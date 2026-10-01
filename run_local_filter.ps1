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

# 云端候选文件缺失时，在 Windows 本地只做“源下载 + 云端结构初筛”，
# 不在这一阶段进行节点网络测试。
if(!(Test-Path ".\output\candidates-general.yaml") -or !(Test-Path ".\output\candidates-chatgpt.yaml")){
  if(!$NoSourceRefresh -and (Test-Path ".\update_sources.sh")){
    Write-Host "Split candidate files missing: refreshing public source snapshots..."
    $Bash=(Get-Command bash.exe -ErrorAction SilentlyContinue)
    if($Bash){
      & $Bash.Source ".\update_sources.sh"
      if($LASTEXITCODE -ne 0){throw "update_sources.sh failed"}
    } else {
      Write-Host "bash.exe not found; using existing snapshots if available."
    }
  }

  Write-Host "Building split cloud candidate pools..."
  & $Python ".\cloud_candidates.py"
  if($LASTEXITCODE -ne 0){throw "cloud candidate build failed"}
}

$FilterArgs=@(
  ".\local_mihomo_filter.py",
  "--mihomo",$Mihomo,
  "--general-limit",$GeneralLimit,
  "--chatgpt-limit",$ChatGPTLimit,
  "--concurrency",$Concurrency
)
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
    throw "Publish blocked: one or both router pools are unexpectedly small; previous GitHub output is kept."
  }

  $Status=git status --porcelain
  if($Status){throw "Publish blocked because the working tree has local changes."}

  git add output/nikki-general.yaml output/nikki-chatgpt.yaml output/nikki.yaml output/local-test-report.json cache/node-cache.json
  git diff --cached --quiet
  if($LASTEXITCODE -ne 0){
    git commit -m "publish local mihomo node pools"
    git push origin main
  }
}

Write-Host "Done."
