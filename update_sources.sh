#!/bin/bash

set -e

mkdir -p input/JP
mkdir -p input/HK
mkdir -p input/SG


echo "Updating JP..."

curl -L \
https://raw.githubusercontent.com/Au1rxx/free-vpn-subscriptions/main/output/country/JP/clash-0001.yaml \
-o input/JP/clash-0001.yaml


echo "Updating HK..."

curl -L \
https://raw.githubusercontent.com/Au1rxx/free-vpn-subscriptions/main/output/country/HK/clash-0001.yaml \
-o input/HK/clash-0001.yaml


echo "Updating SG..."

curl -L \
https://raw.githubusercontent.com/Au1rxx/free-vpn-subscriptions/main/output/country/SG/clash-0001.yaml \
-o input/SG/clash-0001.yaml


echo "Sources updated"