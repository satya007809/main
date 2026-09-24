# Uninstall-Houdini.ps1 - fully removes Houdini 21.0.440 from Windows.
# Run: right-click PowerShell -> "Run as administrator", then:
#   Set-ExecutionPolicy -Scope Process Bypass -Force; & "$HOME\Downloads\Uninstall-Houdini.ps1"

$ErrorActionPreference = 'SilentlyContinue'
$ver = '21.0.440'

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole('Administrators')) {
    Write-Host 'Please run this script as Administrator.' -ForegroundColor Red; exit 1
}

Write-Host "This will completely remove Houdini $ver." -ForegroundColor Yellow
$wipePrefs = (Read-Host 'Also delete your prefs/shelves in Documents\houdini21.0 (a backup zip is made on Desktop first)? [y/N]') -eq 'y'
$wipeLicense = (Read-Host 'Also remove SideFX License Server + Launcher (only if no other SideFX version is installed)? [y/N]') -eq 'y'
if ((Read-Host 'Proceed? [y/N]') -ne 'y') { exit }

# 1. Stop processes
Write-Host '[1/6] Stopping Houdini processes...'
'houdini','houdinifx','houdinicore','hindie','hython','hserver','hkey','houdini_launcher','sesinetd' |
    ForEach-Object { Stop-Process -Name $_ -Force }
if ($wipeLicense) { Stop-Service -Name 'HoudiniLicenseServer','sesinetd' -Force }

# 2. Run official uninstallers from the registry
Write-Host '[2/6] Running official uninstallers...'
$keys = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*'
$pattern = if ($wipeLicense) { 'Houdini|SideFX|Side Effects' } else { "Houdini $ver|SideFX Labs" }
Get-ItemProperty $keys | Where-Object { $_.DisplayName -match $pattern } | ForEach-Object {
    Write-Host "   Uninstalling $($_.DisplayName)"
    $cmd = if ($_.QuietUninstallString) { $_.QuietUninstallString } else { $_.UninstallString }
    if ($cmd -match '^"?(.+?\.exe)"?\s*(.*)$') {
        $args = $Matches[2]; if ($args -notmatch '/S') { $args = "$args /S".Trim() }
        Start-Process -FilePath $Matches[1] -ArgumentList $args -Wait
    }
}

# 3. Delete leftover program folders
Write-Host '[3/6] Removing leftover folders...'
$sfx = 'C:\Program Files\Side Effects Software'
Remove-Item "$sfx\Houdini $ver" -Recurse -Force
Remove-Item "$env:TEMP\houdini_temp" -Recurse -Force
Remove-Item "$env:LOCALAPPDATA\SideFX" -Recurse -Force
if ($wipeLicense) {
    Remove-Item $sfx -Recurse -Force
    Remove-Item "$env:APPDATA\SideFX" -Recurse -Force
    Remove-Item 'C:\ProgramData\SideFX' -Recurse -Force
}
if ($wipePrefs) {
    $prefs = [Environment]::GetFolderPath('MyDocuments') + '\houdini21.0'
    if (Test-Path $prefs) {
        $zip = [Environment]::GetFolderPath('Desktop') + '\houdini21.0_prefs_backup.zip'
        Compress-Archive -Path $prefs -DestinationPath $zip -Force
        Write-Host "   Prefs backed up to $zip"
        Remove-Item $prefs -Recurse -Force
    }
}

# 4. Shortcuts
Write-Host '[4/6] Removing shortcuts...'
Remove-Item "C:\Users\Public\Desktop\Houdini*$ver*.lnk" -Force
Remove-Item "$([Environment]::GetFolderPath('Desktop'))\Houdini*$ver*.lnk" -Force
Get-ChildItem 'C:\ProgramData\Microsoft\Windows\Start Menu\Programs' -Recurse -Filter "*Houdini*$ver*" |
    Remove-Item -Recurse -Force

# 5. Environment variables
Write-Host '[5/6] Cleaning environment variables...'
foreach ($scope in 'User','Machine') {
    [Environment]::GetEnvironmentVariables($scope).Keys | Where-Object { $_ -like 'HOUDINI*' } |
        ForEach-Object { [Environment]::SetEnvironmentVariable($_, $null, $scope) }
    $path = [Environment]::GetEnvironmentVariable('Path', $scope)
    if ($path) {
        $clean = ($path -split ';' | Where-Object { $_ -and $_ -notmatch "Houdini $ver" }) -join ';'
        [Environment]::SetEnvironmentVariable('Path', $clean, $scope)
    }
}

# 6. Registry (backed up to Desktop first)
Write-Host '[6/6] Cleaning registry...'
$desk = [Environment]::GetFolderPath('Desktop')
reg export 'HKCU\Software\Side Effects Software' "$desk\sidefx_hkcu_backup.reg" /y | Out-Null
reg export 'HKLM\SOFTWARE\Side Effects Software' "$desk\sidefx_hklm_backup.reg" /y | Out-Null
Remove-Item "HKCU:\Software\Side Effects Software\Houdini $ver" -Recurse -Force
Remove-Item "HKLM:\SOFTWARE\Side Effects Software\Houdini $ver" -Recurse -Force
if ($wipeLicense) {
    Remove-Item 'HKCU:\Software\Side Effects Software' -Recurse -Force
    Remove-Item 'HKLM:\SOFTWARE\Side Effects Software' -Recurse -Force
}

Write-Host "`nDone. Houdini $ver removed. Restart your PC to finish." -ForegroundColor Green
