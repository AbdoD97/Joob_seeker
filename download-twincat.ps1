$ProgressPreference = 'SilentlyContinue'

# Step 1: Get MediaFire direct download link
Write-Output 'Fetching download link from MediaFire...'
$page = Invoke-WebRequest -Uri 'https://www.mediafire.com/file/dstdacj3gk7f1ec/[plc247.com]TwinCAT3.1_Beckhoff.rar/file' -UseBasicParsing
$dl = ($page.Links | Where-Object { $_.href -match 'download.*mediafire' -and $_.href -notmatch 'repair' } | Select-Object -First 1).href

if (-not $dl) {
    Write-Output 'ERROR: Could not find download link'
    exit 1
}

Write-Output "Download URL: $dl"
Write-Output 'Downloading TwinCAT 3.1 (this may take a few minutes)...'

# Step 2: Download
Invoke-WebRequest -Uri $dl -OutFile 'C:\temp\TwinCAT3.1.rar'

$size = [math]::Round((Get-Item 'C:\temp\TwinCAT3.1.rar').Length / 1MB, 1)
Write-Output "Downloaded: C:\temp\TwinCAT3.1.rar ($size MB)"
