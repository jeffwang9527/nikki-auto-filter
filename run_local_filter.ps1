param(
    [string]$Mihomo="C:\VPN\v2rayN-7.24.9\v2rayN-windows-64\bin\mihomo\mihomo-windows-amd64-v1.exe",
    [int]$GeneralLimit=12,
    [int]$ChatGPTLimit=8,
    [int]$Concurrency=6,
    [switch]$Full,
    [switch]$Publish,
    [switch]$NoPull,
    [switch]$NoSourceRefresh
)
$ErrorActionPreference="Stop"
Set-Location $PSScriptRoot
$Python="C:\ComfyUI-aki\ComfyUI-aki-v1.6\python\python.exe"
# Keep your known mihomo path compatible with the existing v2rayN installation.
# If the default path above is not found, pass -Mihomo with the exact executable path.
if(!(Test-Path $Python)){throw "Python not found: $Python"}
if(!(Test-Path $Mihomo)){throw "mihomo not found: $Mihomo"}

if(!$NoPull){
  $Branch=(git branch --show-current).Trim()
  if(!$Branch){throw "Unable to detect current git branch."}
  git pull --rebase --autostash origin $Branch
  if($LASTEXITCODE -ne 0){throw "git pull failed on $Branch"}
}

& $Python -m pip install -r requirements.txt
if($LASTEXITCODE -ne 0){throw "pip install failed"}

# A feature branch is not automatically executed by the scheduled GitHub job.
# Therefore the Windows runner bootstraps the cloud candidate file locally when it is absent.
# It still uses only source refresh + structural cleanup here; local network testing remains below.
if(!(Test-Path ".\output\candidates.yaml")){
  if(!$NoSourceRefresh){
    if(Test-Path ".\update_sources.sh"){
      Write-Host "Candidate file missing: refreshing cloud source snapshots locally..."
      # Windows may not have bash; Git for Windows normally supplies it as bash.exe.
      $Bash=(Get-Command bash.exe -ErrorAction SilentlyContinue)
      if($Bash){
        & $Bash.Source ".\update_sources.sh"
        if($LASTEXITCODE -ne 0){throw "update_sources.sh failed"}
      } else {
        Write-Host "bash.exe not found; using existing input snapshots."
      }
    }
  }
  Write-Host "Building output\candidates.yaml..."
  & $Python ".\cloud_candidates.py"
  if($LASTEXITCODE -ne 0){throw "cloud candidate build failed"}
}

$FilterArgs=@(".\local_mihomo_filter.py","--mihomo",$Mihomo,"--general-limit",$GeneralLimit,"--chatgpt-limit",$ChatGPTLimit,"--concurrency",$Concurrency)
if($Full){$FilterArgs+="--full"}
& $Python @FilterArgs
if($LASTEXITCODE -ne 0){throw "local filter failed"}

$Report=Get-Content ".\output\local-test-report.json" -Raw | ConvertFrom-Json
Write-Host ("Selected: general={0}, chatgpt={1}, total={2}" -f $Report.selected_general,$Report.selected_chatgpt,$Report.selected_total)

if($Publish){
  $MinGeneral=[Math]::Max(8,[Math]::Floor($GeneralLimit*0.67))
  $MinChatGPT=[Math]::Max(5,[Math]::Floor($ChatGPTLimit*0.625))
  $MinTotal=[Math]::Max(14,[Math]::Floor(($GeneralLimit+$ChatGPTLimit)*0.70))
  if($Report.selected_general -lt $MinGeneral -or $Report.selected_chatgpt -lt $MinChatGPT -or $Report.selected_total -lt $MinTotal){
    throw "Publish blocked: pool too small; previous GitHub output is kept."
  }
  $Status=git status --porcelain
  if($Status){throw "Publish blocked because the working tree has local changes."}
  git add output/nikki-general.yaml output/nikki-chatgpt.yaml output/nikki.yaml output/local-test-report.json
  git diff --cached --quiet
  if($LASTEXITCODE -ne 0){git commit -m "publish local mihomo node pools";git push origin main}
}
Write-Host "Done."
