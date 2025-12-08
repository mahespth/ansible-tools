#!powershell
#Requires -Module Ansible.Basic

<#
.SYNOPSIS
    Manage "name: X" machine blocks in a text config file on Windows.

.DESCRIPTION
    This module manages blocks of the form:

        name: server1
        ip: 10.0.0.1
        os: windows
        role: web

    Each "machine block" starts with a 'name: <machine>' line and is followed by
    zero or more 'key: value' lines. Blocks are separated by a blank line or EOF.

    The module can:
      - Ensure a machine block is present.
      - Update attributes for a machine block (replace or merge).
      - Remove a machine block.
      - Optionally create a backup of the file before modification.

.PARAMETER path
    Path to the configuration file to edit.

.PARAMETER name
    The machine name (from the 'name: <value>' line) to manage.

.PARAMETER attributes
    A dictionary of 'key: value' pairs for the machine block.

.PARAMETER state
    Whether the block should be present or absent.
    Valid values: 'present', 'absent'.
    Default: 'present'.

.PARAMETER mode
    How to handle attributes when state=present and the block already exists:
      - 'replace': Replace all existing attributes with the given attributes.
      - 'merge'  : Merge with existing attributes (update/add keys in attributes).
    Default: 'replace'.

.PARAMETER backup
    Whether to create a backup of the file before editing.
    If true and backup_path/backup_name are not set, a backup file is created
    next to the original file, named "<original>.<timestamp>", similar to
    ansible.builtin.lineinfile.

.PARAMETER backup_path
    Optional path (directory) where the backup file will be created.
    If omitted, the directory of 'path' is used.

.PARAMETER backup_name
    Optional name of the backup file (file name only, not a full path).
    If omitted, a name is generated based on the original file name and a
    timestamp: "<original_basename>.<timestamp>".

.NOTES
    Author: Your Name <you@example.com>
    Module: win_machine_config
    Requires: Windows Server 2016+ (PowerShell 5+), Ansible.Basic

.EXAMPLE
    - name: Ensure server1 definition is present (replace attrs)
      win_machine_config:
        path: C:\configs\machines.txt
        name: server1
        attributes:
          ip: 10.0.1.20
          os: windows
          role: web
          env: prod
        state: present
        mode: replace
        backup: true

.EXAMPLE
    - name: Ensure server2 definition is present (merge attrs) with custom backup
      win_machine_config:
        path: C:\configs\machines.txt
        name: server2
        attributes:
          ip: 10.0.2.30
        state: present
        mode: merge
        backup: true
        backup_path: C:\configs\backups
        backup_name: machines-backup.txt

.EXAMPLE
    - name: Remove server3 definition
      win_machine_config:
        path: C:\configs\machines.txt
        name: server3
        state: absent
        backup: true
#>

Import-Module Ansible.Basic

# ----- Argument spec -----
$spec = @{
    path = @{
        type     = 'str'
        required = $true
    }
    name = @{
        type     = 'str'
        required = $true
    }
    attributes = @{
        type     = 'dict'
        required = $false
        default  = @{}
    }
    state = @{
        type     = 'str'
        choices  = @('present', 'absent')
        default  = 'present'
    }
    mode = @{
        type     = 'str'
        choices  = @('replace', 'merge')
        default  = 'replace'
    }
    backup = @{
        type    = 'bool'
        default = $false
    }
    backup_path = @{
        type    = 'str'
        required = $false
    }
    backup_name = @{
        type    = 'str'
        required = $false
    }
}

$params = Parse-Args -Arguments $args -ParameterSpec $spec -SupportsCheckMode $true

$path        = $params.path
$name        = $params.name
$attributes  = [hashtable]$params.attributes
$state       = $params.state
$mode        = $params.mode
$backup      = [bool]$params.backup
$backupPath  = $params.backup_path
$backupName  = $params.backup_name
$checkMode   = [bool]$params._ansible_check_mode

$result = @{
    changed = $false
    path    = $path
    name    = $name
}

# ----- Helpers -----

function Get-Newline {
    param(
        [string]$Content
    )

    if ($Content -match "`r`n") { return "`r`n" }
    else { return "`n" }
}

function Parse-Blocks {
    param(
        [string]$Content
    )

    $blocks = @()

    if ([string]::IsNullOrWhiteSpace($Content)) {
        return $blocks
    }

    # Split on one or more blank lines (Windows or Unix line endings)
    $rawBlocks = $Content -split "(\r?\n){2,}"

    foreach ($raw in $rawBlocks) {
        if ([string]::IsNullOrWhiteSpace($raw)) { continue }

        $lines = $raw -split "\r?\n"
        if ($lines.Count -eq 0) { continue }

        $first = $lines[0]

        $block = [ordered]@{
            Name     = $null          # machine name or $null
            Lines    = $lines         # array of text lines (no newline chars)
            RawLines = $lines.Clone() # original, for non-machine blocks
        }

        if ($first -match '^\s*name:\s*(.+)$') {
            $block.Name = $matches[1].Trim()
        }

        $blocks += ,$block
    }

    return $blocks
}

function Get-AttributesFromBlock {
    param(
        $Block
    )

    $attrs = @{}

    # Skip first line (name: ...)
    for ($i = 1; $i -lt $Block.Lines.Count; $i++) {
        $line = $Block.Lines[$i]

        if ($line -match '^\s*([^:#]+):\s*(.*?)\s*$') {
            $key = $matches[1].Trim()
            $val = $matches[2].Trim()
            if ($key) {
                $attrs[$key] = $val
            }
        }
    }

    return $attrs
}

function Render-MachineBlock {
    param(
        [string]$Name,
        [hashtable]$Attrs,
        [string]$Newline
    )

    $lines = @()
    $lines += "name: $Name"

    foreach ($k in ($Attrs.Keys | Sort-Object)) {
        $v = $Attrs[$k]
        $lines += "$k: $v"
    }

    # Join with newline, and ensure a newline at the end
    $text = ($lines -join $Newline) + $Newline
    return $text
}

# Create backup with semantics similar to lineinfile, plus optional path/name
function New-BackupFile {
    param(
        [string]$TargetPath,
        [string]$BackupPath,
        [string]$BackupName
    )

    $targetDir  = Split-Path -Path $TargetPath -Parent
    $targetBase = Split-Path -Path $TargetPath -Leaf

    # Determine directory
    if ($BackupPath -and $BackupPath.Trim() -ne '') {
        $dir = $BackupPath
    }
    else {
        $dir = $targetDir
    }

    # Determine filename
    if ($BackupName -and $BackupName.Trim() -ne '') {
        $fileName = $BackupName
    }
    else {
        # lineinfile-like: original basename + timestamp
        $timestamp = Get-Date -Format 'yyyyMMddHHmmss'
        $fileName = "$targetBase.$timestamp"
    }

    # Ensure directory exists
    if ($dir -and -not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }

    $fullPath = Join-Path -Path $dir -ChildPath $fileName
    Copy-Item -LiteralPath $TargetPath -Destination $fullPath -ErrorAction Stop
    return $fullPath
}

# ----- Main logic -----

try {
    $content = ""
    $fileExists = Test-Path -LiteralPath $path

    if ($fileExists) {
        $content = Get-Content -LiteralPath $path -Raw -ErrorAction Stop
    }

    $newline = Get-Newline -Content $content
    if (-not $content) {
        # If file is empty/non-existent, default to Windows newline
        $newline = "`r`n"
    }

    $blocks = Parse-Blocks -Content $content
    $changed = $false
    $targetFound = $false

    $newBlocksText = New-Object System.Collections.Generic.List[string]

    foreach ($blk in $blocks) {
        if ($blk.Name -ne $name) {
            # Not our target block – keep as-is
            $newBlocksText.Add(($blk.RawLines -join $newline))
            continue
        }

        $targetFound = $true

        if ($state -eq 'absent') {
            # Drop this block
            $changed = $true
            continue
        }

        # state == present
        $currentAttrs = Get-AttributesFromBlock -Block $blk

        if ($mode -eq 'replace') {
            $merged = @{}
            foreach ($k in $attributes.Keys) { $merged[$k] = $attributes[$k] }
        }
        else {
            # merge
            $merged = @{}
            foreach ($k in $currentAttrs.Keys) { $merged[$k] = $currentAttrs[$k] }
            foreach ($k in $attributes.Keys)   { $merged[$k] = $attributes[$k] }
        }

        # Compare old vs new attributes
        $same = $true
        if ($merged.Keys.Count -ne $currentAttrs.Keys.Count) {
            $same = $false
        }
        else {
            foreach ($k in $merged.Keys) {
                if (-not $currentAttrs.ContainsKey($k) -or $currentAttrs[$k] -ne $merged[$k]) {
                    $same = $false
                    break
                }
            }
        }

        if (-not $same) {
            $changed = $true
        }

        # Render updated block
        $newBlocksText.Add((Render-MachineBlock -Name $name -Attrs $merged -Newline $newline))
    }

    # If block not found and we want it present → append
    if (($state -eq 'present') -and (-not $targetFound)) {
        $changed = $true
        $newBlocksText.Add((Render-MachineBlock -Name $name -Attrs $attributes -Newline $newline))
    }

    # If file existed and we removed its only block, we might end up empty
    $newContent = ($newBlocksText -join ($newline + $newline))

    if (-not $fileExists -and -not $changed -and $state -eq 'present') {
        # new file, new block
        $changed = $true
    }

    $result.changed = $changed

    if ($checkMode) {
        Exit-Json -obj $result
    }

    if ($changed) {
        if ($backup -and $fileExists) {
            $backupFullPath = New-BackupFile -TargetPath $path -BackupPath $backupPath -BackupName $backupName
            $result.backup_file = $backupFullPath
        }

        # Ensure directory for target exists
        $dir = Split-Path -Path $path -Parent
        if ($dir -and -not (Test-Path -LiteralPath $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }

        [System.IO.File]::WriteAllText($path, $newContent, [System.Text.Encoding]::UTF8)
    }

    Exit-Json -obj $result

}
catch {
    $err = $_.Exception.Message
    Fail-Json -message "win_machine_config failed: $err" -obj $result
}
