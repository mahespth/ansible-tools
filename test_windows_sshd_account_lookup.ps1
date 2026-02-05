# Define the Advapi32.dll function
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public class Advapi32 {
    [DllImport("advapi32.dll", CharSet = CharSet.Auto, SetLastError = true)]
    public static extern bool LookupAccountName(
        string lpSystemName,
        string lpAccountName,
        byte[] Sid,
        ref uint cbSid,
        System.Text.StringBuilder ReferencedDomainName,
        ref uint cchReferencedDomainName,
        out uint peUse
    );
}
"@

# Parameters
$systemName = $null  # Local system
$accountName = "sshd"  # Replace with the account name you want to query
$sid = New-Object byte[] 256  # Allocate space for the SID
$sidSize = $sid.Length
$domainName = New-Object System.Text.StringBuilder 256
$domainNameSize = [uint32]256
$sidType = [uint32]0

# Call the function
$result = [Advapi32]::LookupAccountName(
    $systemName,
    $accountName,
    $sid,
    [ref]$sidSize,
    $domainName,
    [ref]$domainNameSize,
    [ref]$sidType
)

# Debugging Output
if ($result) {
    Write-Host "LookupAccountName succeeded!"
    Write-Host "SID: $([BitConverter]::ToString($sid, 0, $sidSize))"
    Write-Host "Referenced Domain Name: $domainName"
    Write-Host "SID Type: $sidType"
} else {
    $errorCode = [System.Runtime.InteropServices.Marshal]::GetLastWin32Error()
    Write-Host "LookupAccountName failed with error code: $errorCode"
    Write-Host "Error Message: $([ComponentModel.Win32Exception]::new($errorCode).Message)"
}
 
