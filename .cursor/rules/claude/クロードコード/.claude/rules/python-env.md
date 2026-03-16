---
paths:
  - "**/*.py"
  - "Discord*/**"
---

# Python環境ルール

このプロジェクトのPython実行環境に関するルール。

## 必須事項

- Pythonバージョン：3.14（`/opt/homebrew/bin/python3`）
- `distutils` は削除済みのため `japanize_matplotlib` は**使用禁止**
- パッケージインストールは必ず `--break-system-packages` オプションを付ける

```bash
pip3 install パッケージ名 --break-system-packages
```

## matplotlibの日本語フォント

`japanize_matplotlib` の代わりに以下を使用する：

```python
plt.rcParams['font.family'] = 'Hiragino Sans'
```

## 絵文字・特殊文字の注意

Hiragino Sans で表示できない文字は警告が出るため、以下を使う：
- ✓ → `◯`
- ✗ → `×`
- 絵文字（📋など）→ テキストに置き換える
