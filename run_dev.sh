#!/bin/bash
# run_dev.sh - Booklight AI 開発サーバー起動スクリプト

# 色の定義
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Booklight AI 開発環境起動スクリプト ===${NC}"
echo -e "${YELLOW}両方のサーバーを起動します...${NC}"

# 現在のディレクトリを保存
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# FastAPIバックエンド起動
echo -e "${GREEN}FastAPIバックエンドを起動しています...${NC}"
cd "$SCRIPT_DIR/api" && uvicorn app.main:app --reload --port 8000 &
API_PID=$!

# 少し待機してからフロントエンドを起動
sleep 2

# Reactフロントエンド起動
echo -e "${GREEN}Reactフロントエンドを起動しています...${NC}"
cd "$SCRIPT_DIR/frontend" && npm run dev &
FRONTEND_PID=$!

# 終了時の処理
cleanup() {
  echo -e "\n${YELLOW}サーバーを停止しています...${NC}"
  kill $API_PID $FRONTEND_PID
  echo -e "${GREEN}すべてのサーバーが停止しました。${NC}"
  exit
}

# Ctrl+C で終了時にクリーンアップ
trap cleanup INT TERM

echo -e "${GREEN}両方のサーバーが起動しました！${NC}"
echo -e "${BLUE}バックエンド: ${NC}http://localhost:8000"
echo -e "${BLUE}フロントエンド: ${NC}http://localhost:5173"
echo -e "${YELLOW}終了するには Ctrl+C を押してください${NC}"

# プロセスが終了するのを待機
wait
