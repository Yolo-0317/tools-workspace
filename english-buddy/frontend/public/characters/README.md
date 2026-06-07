# 角色头像

路径：`frontend/public/characters/`（公网 `/english/characters/`）

| 文件名前缀 | 角色 |
|-----------|------|
| `elsa` | 艾莎 |
| `ultra` | 奥特曼 |

页面会 **优先加载 `.jpg`**，没有则自动回退 **`.svg`**。

自备官方/立绘图：放同名 `elsa.jpg` 等（建议 512×512 正方形），然后：

```bash
cd english-buddy && ./scripts/restart.sh --build
```

**公网头像不显示 / 裂图**：多半是 `frontend/dist/characters/*.jpg` 未随 `public/` 一起构建；旧版后端还会对缺失 `.jpg` 误返回 `index.html`。务必带 `VITE_BASE_PATH=/english/` 构建并重启 launchd。
