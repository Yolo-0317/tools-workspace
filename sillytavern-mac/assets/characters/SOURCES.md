# 角色头像来源

仅供个人 SillyTavern 使用；勿用于商业再分发。

| 角色 | 文件 | 来源 |
|------|------|------|
| 鬼瑶儿 | `avatars/鬼瑶儿.png` | 《美女江山一锅煮》第三卷封面（豆瓣 subject/2196210，河南文艺出版社） |
| 战天风 | `avatars/战天风.png` | 《美女江山一锅煮》第四卷封面（豆瓣 subject/2314473） |
| 苏晨 | `avatars/苏晨.png` | Wikimedia Commons：`Ye_Xiaoluan_-_Baimei_xinyong.jpg`（《百美新詠》叶小鸾，公域） |

重建流程：

```bash
bash scripts/fetch-character-avatars.sh
node scripts/build-character-guiyaer.js
node scripts/build-character-zhantianfeng.js
node scripts/build-character-suchen.js
```
