# 公众号 AI 写作与接口对接笔记

> 版本：2026-08-03 · 牛马也智能整理  
> **范围**：用大模型写可读的热点评论稿 + 社会热点排版语气 + 常见 AI 味避坑 + 微信公众平台开放接口对接。  
> **不含**：选题策略、流量运营、账号内部 SOP。

---

## 一、AI 写作：先定口吻

热点评论不是研报，也不是热搜摘要。目标语气：**像在转述公开报道的朋友**——有事实、有判断，但不震惊、不喊单、不装内行。

写 prompt 或改稿时记住：

| 要做 | 别做 |
|------|------|
| 先丢时间、人物、数字、一句原话 | 先写「刷到热搜」「今天我们来聊」 |
| 长短句交错，一段一事 | 逗号串短短语：`戏份砍了，进度飞，台词听不懂` |
| 社会争议呈现多方，不下定论 | 替司法/当事人判刑 |
| 网友原话放引号里 | 叙述层模仿弹幕缩写 |

**给模型的指令示例**（可按需改）：

```text
写一篇 1800 字左右的热点评论，纯段落，不要小标题。
口吻：像在跟朋友转述公开报道，不要导读腔、不要热榜播报、不要对称排比。
首段直接写谁+发生了什么；社会话题须呈现多方观点。
禁止：综上所述、值得注意的是、写到这儿就够、不是A而是B连用。
```

---

## 二、社会热点评论：排版、语气与感情

适合社会、民生、公共事件类稿件。与下一节「开头禁词」并用。

### 2.1 排版

| 手法 | 做法 |
|------|------|
| 极短段 | 多数段 1–3 行；关键事实可单句成段 |
| 加粗 | 全文约 3–5 处，只标核心判断，勿满篇标重点 |
| 引用块 | 通报摘录、学生留言、当事人原话用引用格式，与叙述分开 |
| 分号排比 | 引用内用分号罗列细节：`是一个会修车的；是一个会打招呼的；是一个……` |

不要靠「一、二、三」小标题撑结构；用空行和「可是」「然而」转折。

### 2.2 开头

**冷事实连打**（推荐）：

```text
前天，一所大学死了一个人。
是一个宿管大爷，热死的。
```

也可用 **一句环境反差** 点出割裂，立刻回到人名与事实；不要从「刷到热搜」写起。

### 2.3 中立立人：用物件，不用形容词

| 弱 | 强 |
|----|-----|
| 他很善良，生活很苦 | 八个月没发工资，多数日子清水煮挂面；学生不要的棉袄，他叠好留着过冬 |
| 学校态度冷漠 | 通报里只有「物业工作人员」六个字，没有姓名 |

### 2.4 对照骨架

1. 写清 **通报/声明里的模糊说法**  
2. 再写 **旁人记忆里的具体名字与细节**  
3. 必要时加粗一句对照  

争议案件类：按时间线写（报警 → 刑拘 → 判决 → 新进展），各方网上说法都点到，**司法未结不下定论**。

### 2.5 语气与感情

- **克制**：惋惜、不解、愤怒落在事实上，少用「震惊」「三观震碎」「天都塌了」  
- **视角**：用「试想」「若站在……一方」「不少学生记得」，少连续「我觉得」「今天我想写」  
- **递进**：事实（冷）→ 细节（温）→ 对照（张力）→ 公共议题（一两句）→ 名字或问句收尾  

结尾优先：**名字 + 关键事实**，或一句问句留给读者。

### 2.6 生成 prompt 可追加

```text
社会热点：短段排版；物件立人；通报模糊称谓 vs 民间具体记忆；引用块放原话；
加粗不超过 5 处；感情克制；司法未结勿下定论；禁止震惊体与第一人称「我」连用。
```

---

## 三、开头：首段只写「人 + 事」

| 别这样写 | 可以这样写 |
|----------|------------|
| 刷到这条热搜，第一反应是又要吵。 | 上海朱女士，2006 年结婚……丈夫却跟第三者拿假结婚证去医院做试管。 |
| 百度把这事送上热搜，微博也在转。 | 暑期档票房刚过 70 亿，《八仙》成了国产片里讨论最多的一部。 |
| 今天我们来聊一下选角争议。 | 胡一天在新剧里演高中生，播了两集，评论区已经吵成两派。 |

**首段禁用**：`刷到这条热搜` · `第一反应` · `往下翻才知道` · `今天我们来聊` · `值得注意的是`

**热榜播报禁用**：`百度送上热搜` · `微博词条#…#` · `热度破亿` · `吵上热搜` — 改成写大家在吵什么；平台名最多自然带过一处。

**抬格调禁用**：小事别写成社会大案。用「吵了一架」「算不上大事但…」，别用「这事闹这么大」「也跟大背景有关」。

---

## 四、正文节奏

1. **事实先行**：时间、地点、数字、可核对的名词，再补一句判断。  
2. **一段一事**：禁止「第一/第二」分节、禁止快讯列表（除非你就是写快讯）。  
3. **完整人话**：叙述层不用弹幕体。

| 叙述层别写 | 改成 |
|------------|------|
| 进度飞、节奏飞 | 剧情推进得太快 / 节奏赶 |
| 眼里没光、班味儿、贴角色 | 写出具体观感（或引号内转述网友） |
| 演技能补、扮嫩 | 演技能不能把年龄差盖住 / 硬扮年轻 |
| 赛道、魔改、劝退（动词） | 这类戏 / 改编离谱 / 一看就不想继续看 |

4. **信息边界**：以公开报道为准；不编采访、不编「内部人士」。

---

## 五、怎么结尾

- 可用 **一句问句** 引留言：「你更站哪一边？」「这类演法你能接受吗？」  
- 正文里 **不要** 堆「欢迎关注」「点赞转发」——关注引导放排版层或后台自动回复。  
- 免责声明由公众号统一加，正文 `body_core` 里通常不写长篇免责。

---

## 六、AI 味与套话（写完后全文搜索）

命中即改：

**结构套话**：`第一/二条线` · `一块…另一块` · `不是A而是B` · `惹眼…其实是` · `吵得最凶` · `说到底` · `写到这儿就够` · `二次发酵`

**假口语**：`挺寒的` · `基本盘` · `落锤` · `从别的口子` · `这茬` · `掰扯一摞`

**机械连接**：`综上所述` · `与此同时` · `不仅如此` · `一方面…另一方面` · `在此背景下`

**营销腔**：`震惊` · `重磅` · `点赞让我知道` · `希望对您有帮助`

**对称排比**：`有流量、有辨识度，片方省事` — 最多保留一处，其余拆开。

**建议 grep 关键词**：

```text
说到底|值得注意的是|写到这儿|一块|另一块|进度飞|眼里没光|班味儿|魔改
```

---

## 七、写完后自检（5 分钟）

- [ ] 首段：人 + 事，无「刷到热搜」  
- [ ] 纯段落，无小标题堆砌  
- [ ] §六 禁词无命中  
- [ ] 无热榜播报连读（平台名 + 词条名）  
- [ ] 社会话题有多方观点，无定论式判决  
- [ ] 朗读一遍：像不像朋友在转述？

---

## 八、微信公众平台 API 对接

官方文档入口：[微信公众平台开发者文档](https://developers.weixin.qq.com/doc/offiaccount/Getting_Started/Overview.html)

以下流程适用于 **服务号/订阅号** 的 **草稿箱 + 发布** 能力（需后台开通相应接口权限）。

### 8.1 前置条件

| 项 | 说明 |
|----|------|
| **AppID / AppSecret** | 公众平台 → 设置与开发 → 基本配置 |
| **IP 白名单** | 调用 API 的服务器公网 IP 须加入白名单；否则会报 `40164` / `61004` |
| **HTTPS** | 所有请求走 `https://api.weixin.qq.com/cgi-bin/` |

环境变量示例（勿把 Secret 提交到 Git）：

```bash
export WECHAT_MP_APPID="wx........"
export WECHAT_MP_SECRET="........"
```

### 8.2 获取 access_token

`client_credential` 模式，有效期约 7200 秒，须本地缓存并在过期前刷新。

```http
GET https://api.weixin.qq.com/cgi-bin/token
  ?grant_type=client_credential
  &appid=APPID
  &secret=APPSECRET
```

响应：

```json
{"access_token":"ACCESS_TOKEN","expires_in":7200}
```

后续接口在 query 带 `access_token=ACCESS_TOKEN`。

### 8.3 图片：封面 vs 正文

| 用途 | 接口 | 返回值 | 说明 |
|------|------|--------|------|
| **封面** | `POST /cgi-bin/material/add_material?type=image` | `media_id` | 填入草稿 `thumb_media_id` |
| **正文插图** | `POST /cgi-bin/media/uploadimg` | `url` | 写入 HTML `<img src="url">` |

正文 `content` 字段必须是 **HTML**；本地 Markdown 须先转成 `<p>`、`<br/>`、`<img>` 等。

### 8.4 新增草稿 `draft/add`

```http
POST https://api.weixin.qq.com/cgi-bin/draft/add?access_token=ACCESS_TOKEN
Content-Type: application/json
```

```json
{
  "articles": [
    {
      "article_type": "news",
      "title": "标题（建议完整表意，搜一搜会截断）",
      "author": "作者名",
      "digest": "摘要，约 120 字内",
      "content": "<p>正文 HTML</p>",
      "thumb_media_id": "封面 media_id",
      "need_open_comment": 1,
      "only_fans_can_comment": 0
    }
  ]
}
```

成功返回 `media_id`（草稿 ID，非图文永久素材 ID）。

### 8.5 更新草稿 `draft/update`

已有草稿只改标题/正文/封面时：

```json
{
  "media_id": "草稿 media_id",
  "index": 0,
  "articles": {
    "title": "新标题",
    "content": "<p>新正文</p>",
    "thumb_media_id": "..."
  }
}
```

`POST /cgi-bin/draft/update?access_token=ACCESS_TOKEN`

### 8.6 发布（可选）`freepublish/submit`

草稿审好后提交发布（非群发，走「发布」能力）：

```json
{"media_id": "草稿 media_id"}
```

`POST /cgi-bin/freepublish/submit?access_token=ACCESS_TOKEN`

群发、定时群发另有 `message/mass/*` 接口；与草稿箱是不同路径，按产品需求选。

### 8.7 最小 Python 示例

```python
import os
import requests

APPID = os.environ["WECHAT_MP_APPID"]
SECRET = os.environ["WECHAT_MP_SECRET"]
BASE = "https://api.weixin.qq.com/cgi-bin"


def get_token() -> str:
    r = requests.get(
        f"{BASE}/token",
        params={"grant_type": "client_credential", "appid": APPID, "secret": SECRET},
        timeout=20,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("errcode"):
        raise RuntimeError(data)
    return data["access_token"]


def upload_cover(token: str, path: str) -> str:
    with open(path, "rb") as f:
        r = requests.post(
            f"{BASE}/material/add_material",
            params={"access_token": token, "type": "image"},
            files={"media": f},
            timeout=60,
        )
    data = r.json()
    if data.get("errcode"):
        raise RuntimeError(data)
    return data["media_id"]


def add_draft(token: str, *, title: str, html: str, thumb_media_id: str) -> str:
    payload = {
        "articles": [{
            "article_type": "news",
            "title": title,
            "author": "笔名",
            "digest": title[:120],
            "content": html,
            "thumb_media_id": thumb_media_id,
            "need_open_comment": 1,
        }]
    }
    r = requests.post(
        f"{BASE}/draft/add",
        params={"access_token": token},
        json=payload,
        timeout=30,
    )
    data = r.json()
    if data.get("errcode"):
        raise RuntimeError(data)
    return data["media_id"]


if __name__ == "__main__":
    token = get_token()
    thumb = upload_cover(token, "cover.jpg")
    media_id = add_draft(
        token,
        title="示例标题",
        html="<p>首段直接写事实。</p><p>第二段补充背景。</p>",
        thumb_media_id=thumb,
    )
    print("draft media_id:", media_id)
```

### 8.8 常见错误

| errcode | 含义 | 处理 |
|---------|------|------|
| 40001 | access_token 无效或过期 | 重新获取 token |
| 40164 / 61004 | IP 不在白名单 | 后台添加服务器公网 IP |
| 45009 | 接口调用超过限制 | 降频、缓存 token |
| 53402 | 封面尺寸不合规 | 换符合规范的 JPG/PNG |

### 8.9 推荐工程习惯

1. **token 落盘缓存**，过期前 60s 刷新，避免每次打 token 接口。  
2. **正文与配图分离**：AI 只产出 `body_core` 纯文本，插图、封面、HTML 由脚本后处理。  
3. **先 draft 后人工**：API 进草稿箱，后台预览无误再发布。  
4. **repush 走 update**：改稿不重跑模型时，用 `draft/update` 覆盖同一 `media_id`。

---

## 九、延伸阅读（官方）

- [获取 access_token](https://developers.weixin.qq.com/doc/offiaccount/Basic_Information/Get_access_token.html)  
- [新增草稿](https://developers.weixin.qq.com/doc/offiaccount/Draft_Box/Add_draft.html)  
- [更新草稿](https://developers.weixin.qq.com/doc/offiaccount/Draft_Box/Update_draft.html)  
- [上传图文消息图片](https://developers.weixin.qq.com/doc/offiaccount/Asset_Management/Adding_Permanent_Assets.html)  

---

*仅供学习交流，转载请注明出处「牛马也智能」。AppSecret 勿泄露、勿写入公开文档。*
