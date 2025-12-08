#!powershell
#Requires -Module Ansible.Basic

<#
.SYNOPSIS
  Manage "name: X" machine blocks in a text config file on Windows.

Each machine block:

  name: server1
  ip: 10.0.0.1
  os: windows
  role: web

Blocks are separated by a blank line (or EOF).
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
}

$params = Parse-Args -Arguments $args -ParameterSpec $spec -SupportsCheckMode $true

$path      = $params.path
$name      = $params.name
$attributes = [hashtable]$params.attributes
$state     = $params.state
$mode      = $params.mode
$backup    = [bool]$params.backup
$checkMode = [bool]$params._ansible_check_mode

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
            $timestamp = Get-Date -Format 'yyyyMMddHHmmss'
            $backupPath = "$path.$timestamp.bak"
            Copy-Item -LiteralPath $path -Destination $backupPath -ErrorAction Stop
            $result.backup_path = $backupPath
        }

        # Ensure directory exists
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