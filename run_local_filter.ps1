param(
    [string]$Mihomo="C:\VPN\v2rayN-7.24.9\v2rayN-windows-64\bin\mihomo\mihomo-windows-amd64-v1.exe",
    [int]$GeneralLimit=12,
    [int]$ChatGPTLimit=8,
    [int]$Concurrency=6,
    [switch]$Full,
    [switch]$Publish,
    [switch]$NoPull
)
$ErrorActionPreference="Stop"
Set-Location $PSScriptRoot
$Python="C:\ComfyUI-aki\ComfyUI-aki-v1.6\python\python.exe"
if(!(Test-Path $Python)){throw "Python not found: $Python"}
if(!(Test-Path $Mihomo)){throw "mihomo not found: $Mihomo"}
if(!$NoPull){
  git pull --rebase --autostash origin main
  if($LASTEXITCODE -ne 0){throw "git pull failed"}
}
& $Python -m pip install -r requirements.txt
if($LASTEXITCODE -ne 0){throw "pip install failed"}
$args=@(".\local_mihomo_filter.py","--mihomo",$Mihomo,"--general-limit",$GeneralLimit,"--chatgpt-limit",$ChatGPTLimit,"--concurrency",$Concurrency)
if($Full){$args+="--full"}
& $Python @args
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
