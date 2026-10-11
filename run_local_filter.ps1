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
$ErrorActionPreference="Continue"
Set-Location $PSScriptRoot
$env:PYTHONIOENCODING="utf-8"

# Network precondition: only run when the PC is booted, Wi-Fi link is up and internet is
# reachable, while the wired Ethernet link is NOT connected. The scheduled task retries via
# RestartInterval until this passes (covers missed runs after boot).
$WiFiOk=$false
$NetOk=$false
$EthernetUp=$false
try{
  $upAdapters=Get-NetAdapter -Physical | Where-Object {$_.Status -eq 'Up'}
  $wifiAdapter=$upAdapters | Where-Object {$_.InterfaceDescription -match 'Wi-?Fi|Wireless|802\.11|WLAN'}
  if($wifiAdapter){$WiFiOk=$true}
  $ethAdapter=$upAdapters | Where-Object {$_.InterfaceDescription -notmatch 'Wi-?Fi|Wireless|802\.11|WLAN|Bluetooth|Virtual|Loopback|TAP|VPN'}
  if($ethAdapter){$EthernetUp=$true}
  $conn=Get-NetConnectionProfile -ErrorAction SilentlyContinue | Where-Object {$_.IPv4Connectivity -eq 'Internet' -or $_.IPv6Connectivity -eq 'Internet'}
  if($conn){$NetOk=$true}
}catch{}
if(!($WiFiOk -and $NetOk -and -not $EthernetUp)){
  Write-Host "Network precondition not met: WiFiUp=$WiFiOk Internet=$NetOk EthernetUp=$EthernetUp. Task will retry via RestartInterval."
  exit 3
}

$Python="C:\ComfyUI-aki\ComfyUI-aki-v1.6\python\python.exe"
if(!(Test-Path $Python)){throw "Python not found: $Python"}
if(!(Test-Path $Mihomo)){throw "mihomo not found: $Mihomo"}

# GitHub 匿名 API 配额低(60次/小时)，freshness 检查易被 403 限流导致候选池为空。
# 源文件已由 bootstrap 实时下载，跳过 freshness 不损失准确性；保留 env 可临时恢复检查。
if(-not $env:NIKKI_SKIP_FRESHNESS){$env:NIKKI_SKIP_FRESHNESS="1"}

if(!$NoPull){
  $Branch=(git branch --show-current).Trim()
  if(!$Branch){throw "Unable to detect current git branch."}
  git pull --rebase --autostash origin $Branch 2>&1 | Out-Null
  if($LASTEXITCODE -ne 0){throw "git pull failed on $Branch"}
}

& $Python -m pip install -r requirements.txt
if($LASTEXITCODE -ne 0){throw "pip install failed"}

# 默认每次运行先刷新公共源快照，再重新生成两套云端候选池。
# -NoSourceRefresh 仅用于你明确要离线复测已有候选时。
$DidRefresh=$false
if(!$NoSourceRefresh){
  Write-Host "Refreshing public source snapshots..."
  if(Test-Path ".\bootstrap_sources.py"){
    & $Python ".\bootstrap_sources.py"
    if($LASTEXITCODE -ne 0){throw "bootstrap_sources.py failed"}
    $DidRefresh=$true
  } else {
    throw "bootstrap_sources.py is missing; pull the latest feature branch first."
  }
}

$NeedBuild=$DidRefresh
if(!(Test-Path ".\output\candidates-general.yaml") -or !(Test-Path ".\output\candidates-chatgpt.yaml")){
  $NeedBuild=$true
}
if($NeedBuild){
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

# A+C: 发布后验证 —— 强制路由器刷新 provider，并按路由器判活标准（www.google.com/generate_204 / chatgpt.com/robots.txt）逐节点测活。
function Verify-RouterPools {
  param(
    [string]$RouterApi="http://192.168.2.1:9090",
    [string]$Secret="885696"
  )
  $Hdr=@{Authorization="Bearer $Secret"}
  Write-Host "Forcing router provider refresh (PUT NIKKI-GENERAL / NIKKI-GPT)..."
  try {
    Invoke-RestMethod -Method Put -Uri "$RouterApi/providers/proxies/NIKKI-GENERAL" -Headers $Hdr -TimeoutSec 40 | Out-Null
    Invoke-RestMethod -Method Put -Uri "$RouterApi/providers/proxies/NIKKI-GPT" -Headers $Hdr -TimeoutSec 40 | Out-Null
  } catch {
    # PUT 失败常见于当前池在路由器判活标准下已死（路由器拉 jsDelivr 也走普通池），
    # 此时不中断，改用现有 provider 状态核查，若存活不足走回滚
    Write-Host "WARNING: provider PUT refresh failed: $($_.Exception.Message). Checking existing provider state instead."
  }
  Start-Sleep -Seconds 8
  $GenProv=Invoke-RestMethod -Uri "$RouterApi/providers/proxies/NIKKI-GENERAL" -Headers $Hdr -TimeoutSec 20
  $GptProv=Invoke-RestMethod -Uri "$RouterApi/providers/proxies/NIKKI-GPT" -Headers $Hdr -TimeoutSec 20
  $GenNames=@($GenProv.proxies | ForEach-Object { $_.name })
  $GptNames=@($GptProv.proxies | ForEach-Object { $_.name })
  Write-Host ("Providers loaded: general={0}, gpt={1}" -f $GenNames.Count, $GptNames.Count)

  $GenAlive=0
  foreach($n in $GenNames){
    $enc=[uri]::EscapeDataString($n)
    try{
      $d=Invoke-RestMethod -Uri ("$RouterApi/proxies/$enc/delay?url=" + [uri]::EscapeDataString("https://www.google.com/generate_204") + "&timeout=6500") -Headers $Hdr -TimeoutSec 12
      if($d.delay -gt 0){$GenAlive++}
    }catch{}
  }
  $GptAlive=0
  foreach($n in $GptNames){
    $enc=[uri]::EscapeDataString($n)
    try{
      $d=Invoke-RestMethod -Uri ("$RouterApi/proxies/$enc/delay?url=" + [uri]::EscapeDataString("https://chatgpt.com/robots.txt") + "&timeout=8500") -Headers $Hdr -TimeoutSec 14
      if($d.delay -gt 0){$GptAlive++}
    }catch{}
  }
  Write-Host ("Router alive check: general={0}/{1}, gpt={2}/{3}" -f $GenAlive, $GenNames.Count, $GptAlive, $GptNames.Count)
  return [pscustomobject]@{general_alive=$GenAlive; general_total=$GenNames.Count; gpt_alive=$GptAlive; gpt_total=$GptNames.Count}
}

if($Publish){
  $MinGeneral=[Math]::Max(8,[Math]::Floor($GeneralLimit*0.67))
  $MinChatGPT=[Math]::Max(5,[Math]::Floor($ChatGPTLimit*0.625))
  $MinTotal=[Math]::Max(14,[Math]::Floor(($GeneralLimit+$ChatGPTLimit)*0.70))

  if($Report.selected_general -lt $MinGeneral -or $Report.selected_chatgpt -lt $MinChatGPT -or $Report.selected_total -lt $MinTotal){
    throw "Publish blocked: one or both router pools are unexpectedly small; previous GitHub output is kept."
  }

  # 将“最终小池”安全发布到 origin/main，不要求当前 feature 工作树干净，
  # 也不会把 feature 分支代码一起推到 main。
  $PublishDir=Join-Path $env:TEMP ("nikki-publish-" + [Guid]::NewGuid().ToString("N"))
  try {
    git fetch origin main
    if($LASTEXITCODE -ne 0){throw "git fetch origin main failed"}

    git worktree add --detach $PublishDir origin/main 2>&1
    if($LASTEXITCODE -ne 0){throw "git worktree add failed"}

    New-Item -ItemType Directory -Force -Path (Join-Path $PublishDir "output") | Out-Null
    Copy-Item ".\output\nikki-general.yaml" (Join-Path $PublishDir "output\nikki-general.yaml") -Force
    Copy-Item ".\output\nikki-chatgpt.yaml" (Join-Path $PublishDir "output\nikki-chatgpt.yaml") -Force
    Copy-Item ".\output\nikki.yaml" (Join-Path $PublishDir "output\nikki.yaml") -Force
    Copy-Item ".\output\local-test-report.json" (Join-Path $PublishDir "output\local-test-report.json") -Force
    if(Test-Path ".\output\nikki-general-previous.yaml"){
      Copy-Item ".\output\nikki-general-previous.yaml" (Join-Path $PublishDir "output\nikki-general-previous.yaml") -Force
    }
    if(Test-Path ".\output\nikki-chatgpt-previous.yaml"){
      Copy-Item ".\output\nikki-chatgpt-previous.yaml" (Join-Path $PublishDir "output\nikki-chatgpt-previous.yaml") -Force
    }

    Push-Location $PublishDir
    $PublishFiles=@(
      "output/nikki-general.yaml",
      "output/nikki-chatgpt.yaml",
      "output/nikki.yaml",
      "output/local-test-report.json"
    )
    if(Test-Path "output/nikki-general-previous.yaml"){
      $PublishFiles += "output/nikki-general-previous.yaml"
    }
    if(Test-Path "output/nikki-chatgpt-previous.yaml"){
      $PublishFiles += "output/nikki-chatgpt-previous.yaml"
    }
    git add @PublishFiles
    git diff --cached --quiet
    if($LASTEXITCODE -ne 0){
      git config user.name "nikki-local-publisher"
      git config user.email "nikki-local-publisher@users.noreply.github.com"
      git commit -m "publish local mihomo node pools"
      if($LASTEXITCODE -ne 0){throw "git commit failed"}
      git push origin HEAD:main 2>&1
      if($LASTEXITCODE -ne 0){throw "git push to main failed"}
    } else {
      Write-Host "No output changes to publish."
    }
    Pop-Location

    # A+C: 发布后路由器强制刷新 + 存活核查，普通池存活数不足则回滚上一池
    $Verify = Verify-RouterPools
    if($Verify.general_alive -lt 4){
      Write-Host "WARNING: router general pool alive < 4. Rolling back to previous pool..."
      if(!(Test-Path ".\output\nikki-general-previous.yaml") -or !(Test-Path ".\output\nikki-chatgpt-previous.yaml")){
        throw "Rollback source missing; previous pools not found. Current (possibly degraded) pool is kept on GitHub."
      }
      Copy-Item ".\output\nikki-general-previous.yaml" ".\output\nikki-general.yaml" -Force
      Copy-Item ".\output\nikki-chatgpt-previous.yaml" ".\output\nikki-chatgpt.yaml" -Force
      git add output/nikki-general.yaml output/nikki-chatgpt.yaml
      git commit -m "rollback to previous node pools (router alive check failed)" 2>&1
      if($LASTEXITCODE -ne 0){throw "rollback commit failed"}
      git push origin HEAD:main 2>&1
      if($LASTEXITCODE -ne 0){throw "rollback push to main failed"}
      Write-Host "Rollback pushed. Verifying again..."
      $Verify2 = Verify-RouterPools
      Write-Host ("After rollback: general={0}/{1}, gpt={2}/{3}" -f $Verify2.general_alive, $Verify2.general_total, $Verify2.gpt_alive, $Verify2.gpt_total)
    }
  } finally {
    if(Test-Path $PublishDir){ git worktree remove --force $PublishDir 2>&1 | Out-Null }
  }
}
Write-Host "Done."
