#!/usr/bin/env bash
# ==============================================================================
# agent-evaluation Skill 一键安装脚本
# 支持：Antigravity (~/.gemini/config/skills) / Claude Code (~/.claude/skills) / 项目工作区 (.agents/skills)
#
# 在线一键安装（全局）：
#   curl -fsSL https://raw.githubusercontent.com/edisonmbli/agent-evaluation-skill/main/install.sh | bash
#
# 在线一键安装到当前项目工作区：
#   curl -fsSL https://raw.githubusercontent.com/edisonmbli/agent-evaluation-skill/main/install.sh | bash -s -- --workspace
#
# 本地克隆后软链接安装（适合开发者同步迭代）：
#   ./install.sh --symlink
# ==============================================================================

set -euo pipefail

SKILL_NAME="agent-evaluation"
REPO_URL="https://github.com/edisonmbli/agent-evaluation-skill.git"

MODE="global"         # global | workspace
TOOL="auto"           # auto | antigravity | claude | all
USE_SYMLINK=0
UNINSTALL=0
WORKSPACE_DIR="$(pwd)"

usage() {
  cat <<EOF
Usage: ./install.sh [OPTIONS]

Options:
  --global              安装到本机全局配置 (默认，对所有项目生效)
  --workspace [DIR]     安装到指定项目目录的 .agents/skills/ 下 (默认当前目录)
  --tool <name>         指定目标工具: auto (默认) | antigravity | claude | all
  --symlink             使用软链接 (ln -s) 而非复制文件 (仅限本地仓库运行)
  --uninstall           卸载已安装的 ${SKILL_NAME} skill
  -h, --help            显示帮助信息
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --global)
      MODE="global"
      shift
      ;;
    --workspace)
      MODE="workspace"
      if [[ $# -gt 1 && ! "$2" =~ ^-- ]]; then
        WORKSPACE_DIR="$2"
        shift
      fi
      shift
      ;;
    --tool)
      TOOL="$2"
      shift 2
      ;;
    --symlink)
      USE_SYMLINK=1
      shift
      ;;
    --uninstall)
      UNINSTALL=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "❌ 未知参数: $1" >&2
      usage
      exit 1
      ;;
  esac
done

# 确定目标安装目录列表
TARGET_DIRS=()
if [[ "$MODE" == "workspace" ]]; then
  TARGET_DIRS+=("${WORKSPACE_DIR}/.agents/skills/${SKILL_NAME}")
else
  case "$TOOL" in
    antigravity)
      TARGET_DIRS+=("${HOME}/.gemini/config/skills/${SKILL_NAME}")
      ;;
    claude)
      TARGET_DIRS+=("${HOME}/.claude/skills/${SKILL_NAME}")
      ;;
    all)
      TARGET_DIRS+=("${HOME}/.gemini/config/skills/${SKILL_NAME}")
      TARGET_DIRS+=("${HOME}/.claude/skills/${SKILL_NAME}")
      ;;
    auto|*)
      # 默认必装 Antigravity 全局目录；如果本机存在 ~/.claude 则同步装入 Claude Code
      TARGET_DIRS+=("${HOME}/.gemini/config/skills/${SKILL_NAME}")
      if [[ -d "${HOME}/.claude" ]]; then
        TARGET_DIRS+=("${HOME}/.claude/skills/${SKILL_NAME}")
      fi
      ;;
  esac
fi

# 卸载模式
if [[ "$UNINSTALL" -eq 1 ]]; then
  for dst in "${TARGET_DIRS[@]}"; do
    if [[ -e "$dst" || -L "$dst" ]]; then
      rm -rf "$dst"
      echo "🗑️  已移除: $dst"
    else
      echo "ℹ️  未找到已安装目录: $dst"
    fi
  done
  exit 0
fi

# 定位源目录：优先检查当前脚本所在仓库，若通过 curl | bash 运行则自动浅克隆到临时目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || pwd)"
SOURCE_SKILL_DIR="${SCRIPT_DIR}/skills/${SKILL_NAME}"
TMP_CLONE_DIR=""

cleanup() {
  if [[ -n "$TMP_CLONE_DIR" && -d "$TMP_CLONE_DIR" ]]; then
    rm -rf "$TMP_CLONE_DIR"
  fi
}
trap cleanup EXIT

if [[ ! -f "${SOURCE_SKILL_DIR}/SKILL.md" ]]; then
  if [[ "$USE_SYMLINK" -eq 1 ]]; then
    echo "❌ --symlink 模式需要先 git clone 仓库到本地再运行 ./install.sh --symlink" >&2
    exit 1
  fi
  echo "📥 正在从 GitHub 获取最新 ${SKILL_NAME} Skill..."
  TMP_CLONE_DIR="$(mktemp -d)"
  git clone --depth 1 "$REPO_URL" "$TMP_CLONE_DIR" >/dev/null 2>&1
  SOURCE_SKILL_DIR="${TMP_CLONE_DIR}/skills/${SKILL_NAME}"
fi

chmod +x "${SOURCE_SKILL_DIR}/scripts/"*.py 2>/dev/null || true

for dst in "${TARGET_DIRS[@]}"; do
  mkdir -p "$(dirname "$dst")"
  rm -rf "$dst"
  if [[ "$USE_SYMLINK" -eq 1 ]]; then
    ln -s "$SOURCE_SKILL_DIR" "$dst"
    echo "✅ 已通过软链接安装至: $dst -> $SOURCE_SKILL_DIR"
  else
    cp -R "$SOURCE_SKILL_DIR" "$dst"
    echo "✅ 已安装至: $dst"
  fi
done

echo ""
echo "🎉 ${SKILL_NAME} Skill 安装完成！"
echo "💡 试试在对话中对 Agent 说："
echo "   - 「用 agent-evaluation 帮我给当前项目做一次评测成熟度体检」"
echo "   - 「用 agent-evaluation 帮我从 0 到 1 搭建这个项目的评测体系」"
