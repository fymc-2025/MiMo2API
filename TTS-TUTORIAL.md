# 🎙️ MiMo2API TTS 高级使用教程

> 本文档详细介绍小米 MiMo TTS v2.5 的各种高级用法，包括风格标签、音频标签、导演模式、唱歌模式等。
> 所有示例都可在 MiMo2API 的 `/v1/audio/speech` 和 `/v1/chat/completions` 端点上直接测试。

---

## 目录

- [快速开始](#快速开始)
- [音色选择](#音色选择)
- [风格标签 `(标签)`](#风格标签-标签)
- [音频标签 `[标签]`](#音频标签-标签-1)
- [自然语言风格控制](#自然语言风格控制)
- [导演模式（角色配音）](#导演模式角色配音)
- [唱歌模式](#唱歌模式)
- [方言与角色扮演](#方言与角色扮演)
- [多风格融合 + 转场](#多风格融合--转场)
- [音色设计](#音色设计)
- [语音克隆](#语音克隆)
- [常见场景配方](#常见场景配方)

---

## 快速开始

最简单的 TTS 调用：

```bash
curl http://localhost:8080/v1/audio/speech \
  -H "Authorization: Bearer sk-mimo" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mimo-v2.5-tts",
    "input": "你好，今天天气真不错！",
    "voice": "冰糖"
  }' --output hello.wav
```

参数说明：

| 参数 | 必填 | 说明 | 默认值 |
|------|------|------|--------|
| `model` | ✅ | 模型名：`mimo-v2.5-tts` / `-voicedesign` / `-voiceclone` | — |
| `input` | ✅ | 要合成的文本 | — |
| `voice` | ❌ | 音色名 | `alloy`→冰糖 |
| `speed` | ❌ | 语速 0.5~2.0 | 1.0 |
| `style` | ❌ | 自然语言风格描述（仅 voicedesign 使用） | — |
| `response_format` | ❌ | 仅支持 `wav` | `wav` |

---

## 模型功能对比

三个 TTS 模型各自支持不同的功能，选错模型会导致某些功能不可用：

| 功能 | `mimo-v2.5-tts` | `mimo-v2.5-tts-voicedesign` | `mimo-v2.5-tts-voiceclone` |
|------|:---:|:---:|:---:|
| 预置音色（冰糖/茉莉/白桦等） | ✅ | ❌ | ❌ |
| 唱歌模式 `(唱歌)` | ✅ **唯一支持** | ❌ | ❌ |
| 风格标签 `(开心)(悲伤)` 等 | ✅ | ❌ | ❌ |
| 音频标签 `[笑][哽咽]` 等 | ✅ | ❌ | ❌ |
| 方言 `(东北话)(粤语)` | ✅ | ❌ | ❌ |
| 角色扮演 `(孙悟空)` | ✅ | ❌ | ❌ |
| 导演模式（角色/场景/指导） | ✅ | ❌ | ❌ |
| 自然语言风格描述 `style` | ✅ | ✅ | ❌ |
| 自定义音色设计（文本描述） | ❌ | ✅ **唯一支持** | ❌ |
| 语音克隆（音频样本） | ❌ | ❌ | ✅ **唯一支持** |
| `voice` 参数 | 预置音色名 | 无效（忽略） | data URI 音频 |

**简单记忆：**
- **`mimo-v2.5-tts`** — 全功能通用，唱歌、标签、方言、导演模式都走它
- **`mimo-v2.5-tts-voicedesign`** — 不要预置音色，用文字描述创造新音色
- **`mimo-v2.5-tts-voiceclone`** — 给一段音频样本，克隆成同样声音

---

## 音色选择

### 预置音色列表

| 音色名 | 语言 | 性别 | 风格 |
|--------|------|------|------|
| `冰糖` | 中文 | 女 | 中性通用，温暖自然 |
| `茉莉` | 中文 | 女 | 柔和亲切，适合温柔对话 |
| `苏打` | 中文 | 男 | 沉稳大气 |
| `白桦` | 中文 | 男 | 低沉叙述感 |
| `Mia` | English | 女 | 明亮活力 |
| `Chloe` | English | 女 | 清澈旋律感 |
| `Milo` | English | 男 | 沉稳男声 |
| `Dean` | English | 男 | 厚重男声 |

### OpenAI 兼容音色名

```bash
# alloy → 冰糖 / echo → 茉莉 / fable → 白桦
# onyx → 苏打 / nova → Mia / shimmer → Chloe
curl ... -d '{"voice": "alloy", ...}'  # 等同 voice=冰糖
```

未在上表的 voice 名会**直接透传**给 MiMo API，所以你也可以试自定义音色名。

---

## 风格标签 `(标签)`

放在 **input 文本开头**，用圆括号包裹。可以同时设置多个风格：

```
(开心)今天真是个好日子！
(温柔 磁性)亲爱的，晚安。
(东北话)哎呀妈呀，太冷了！
```

### 全部风格标签一览

#### 基础情绪

| 标签 | 效果 |
|------|------|
| `(开心)` | 欢快愉悦 |
| `(悲伤)` | 低沉哀伤 |
| `(愤怒)` | 激昂愤怒 |
| `(恐惧)` | 害怕紧张 |
| `(惊讶)` | 意外震惊 |
| `(兴奋)` | 激动亢奋 |
| `(委屈)` | 可怜巴巴 |
| `(平静)` | 平稳叙述 |
| `(冷漠)` | 冷淡疏离 |

#### 复合情绪

`(怅然)` `(欣慰)` `(无奈)` `(愧疚)` `(释然)` `(嫉妒)` `(厌倦)` `(忐忑)` `(动情)`

#### 整体语调

`(温柔)` `(高冷)` `(活泼)` `(严肃)` `(慵懒)` `(俏皮)` `(深沉)` `(干练)` `(凌厉)`

#### 音色定位

`(磁性)` `(醇厚)` `(清亮)` `(空灵)` `(稚嫩)` `(苍老)` `(甜美)` `(沙哑)` `(醇雅)`

#### 人设腔调

`(夹子音)` `(御姐音)` `(正太音)` `(大叔音)` `(台湾腔)`

#### 方言

`(东北话)` `(四川话)` `(河南话)` `(粤语)`

#### 角色扮演

`(孙悟空)` `(林黛玉)`

### 组合示例

```bash
# 多重标签组合
curl ... -d '{
  "input": "(慵懒 磁性)嗯…再睡五分钟就好，真的。"
}'

# 先风格后方言
curl ... -d '{
  "input": "(愤怒 河南话)你咋能这样儿呢！"
}'
```

---

## 音频标签 `[标签]`

嵌入在文本**任意位置**，用方括号包裹。控制局部发音细节：

```
我[叹气]好吧，那就这样吧。
他[紧张]这个……那个……我其实不知道。
```

### 全部音频标签一览

#### 语速与节奏

| 标签 | 效果 |
|------|------|
| `[吸气]` | 吸气声 |
| `[深呼吸]` | 深长吸气 |
| `[叹气]` | 叹气 |
| `[长叹一口气]` | 长叹 |
| `[喘息]` | 呼吸急促 |
| `[屏息]` | 屏住呼吸 |

#### 情绪状态

| 标签 | 效果 |
|------|------|
| `[紧张]` | 声音紧张 |
| `[害怕]` | 声音发怯 |
| `[激动]` | 情绪亢奋 |
| `[疲惫]` | 有气无力 |
| `[委屈]` | 委屈巴巴 |
| `[撒娇]` | 嗲声嗲气 |
| `[心虚]` | 底气不足 |
| `[震惊]` | 极度震惊 |
| `[不耐烦]` | 厌烦语气 |

#### 语音特征

| 标签 | 效果 |
|------|------|
| `[颤抖]` | 声音发抖 |
| `[声音颤抖]` | 同上，更明显 |
| `[变调]` | 音调变化 |
| `[破音]` | 破音效果 |
| `[鼻音]` | 带鼻音说话 |
| `[气声]` | 气声说话 |
| `[沙哑]` | 声音沙哑 |

#### 哭笑表达

| 标签 | 效果 |
|------|------|
| `[笑]` | 轻笑 |
| `[轻笑]` | 更轻的笑 |
| `[大笑]` | 开怀大笑 |
| `[冷笑]` | 冷笑 |
| `[抽泣]` | 抽噎 |
| `[呜咽]` | 低声哭泣 |
| `[哽咽]` | 哭腔说话 |
| `[嚎啕大哭]` | 放声大哭 |

### 标签与其他控制混用

```bash
# 风格标签 + 音频标签 = 最佳效果
curl ... -d '{
  "input": "(悲伤)我[哽咽]真的没有想到会这样……[长叹一口气]算了。"
}'

# 多个音频标签串联
curl ... -d '{
  "input": "[激动]真的吗？！[大笑]太棒了！"
}'

# 自然语言控制 + 标签
curl ... -d '{
  "input": "(温柔)别怕[轻笑]有我在呢。",
  "voice": "茉莉",
  "speed": 0.9
}'
```

---

## 自然语言风格控制

不需要标签，直接在用户消息中用一句话描述想要的风格：

```
用轻快上扬的语调向领导报喜，语速稍快，带着查完成绩后压抑不住的激动与小骄傲。
```

通过 `/v1/chat/completions` 使用，把风格描述放 `user` 消息：

```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer sk-mimo" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mimo-v2.5-tts",
    "messages": [
      {"role": "user", "content": "用轻快上扬的语调，语速稍快，带着激动"},
      {"role": "assistant", "content": "老板！我考上了！"}
    ],
    "audio": {"voice": "冰糖"}
  }'
```

通过 `/v1/audio/speech` 使用，把风格描述放 `style` 参数：

```bash
curl http://localhost:8080/v1/audio/speech \
  -H "Authorization: Bearer sk-mimo" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mimo-v2.5-tts",
    "input": "老板！我考上了！",
    "voice": "冰糖",
    "style": "轻快上扬，语速稍快，带着激动"
  }' --output excited.wav
```

自然语言控制也可以和标签混用——标签定义大的风格框架，自然语言做精细调整。

---

## 导演模式（角色配音）

适合**有声小说、游戏配音、对话场景**。从**角色、场景、指导**三个维度描述：

```
角色：百年门阀岑家的现任大当家，常年深居简出，对人有着极强的阶级疏离感。
场景：在祠堂的阴影里，看着那个不顾一切冲破保安防线来找她的男人。
指导：冰冷、慵懒却极具威压的低语御姐。语速与顿挫极慢，每个字都像是在舌尖滚过才吐出来。
```

### 完整示例

```bash
# 导演模式 via /v1/chat/completions
curl http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer sk-mimo" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mimo-v2.5-tts",
    "messages": [
      {"role": "user", "content": "角色：千年狐妖，见惯世事变迁。场景：月下独酌，对影成三人。指导：慵懒华贵的御姐音，带着看透世事的沧桑感，尾音微微上扬。"},
      {"role": "assistant", "content": "呵，又是几百年过去了[轻笑]你们人类啊，总是这么着急。"}
    ],
    "audio": {"voice": "冰糖"}
  }'
```

```bash
# 导演模式 via /v1/audio/speech（style 参数）
curl http://localhost:8080/v1/audio/speech \
  -H "Authorization: Bearer sk-mimo" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mimo-v2.5-tts",
    "input": "各位观众，欢迎来到决赛现场！我是解说员小杨。",
    "voice": "苏打",
    "style": "角色：体育解说员。场景：万众瞩目的决赛现场，观众席沸腾。指导：语速快而有节奏，声音明亮有穿透力，带着现场直播的紧迫感和激情。"
  }' --output commentary.wav
```

### 导演模式小贴士

- **角色描述越具体越好**：性格、年龄、社会地位、说话习惯
- **场景提供上下文**：环境氛围影响说话方式
- **指导要可感知**：不要写"伤感"，写"声音微微颤抖，尾音拖长"

---

## 唱歌模式

仅 `mimo-v2.5-tts`（基础模型）支持。**必须**以 `(唱歌)` 开头。

### 基础唱歌

```bash
curl http://localhost:8080/v1/audio/speech \
  -H "Authorization: Bearer sk-mimo" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mimo-v2.5-tts",
    "input": "(唱歌)原谅我这一生不羁放纵爱自由",
    "voice": "冰糖"
  }' --output sing.wav
```

### 唱歌 + 情绪标签

```bash
# 悲伤的歌唱
curl ... -d '{
  "input": "(唱歌 悲伤)后来我总算学会了如何去爱",
  "voice": "冰糖"
}'

# 欢快的歌唱
curl ... -d '{
  "input": "(唱歌 开心)今天是个好日子！",
  "voice": "茉莉"
}'
```

### 唱歌 + 音频标签

```bash
curl ... -d '{
  "input": "(唱歌)死了都要爱[高音]不淋漓尽致不痛快",
  "voice": "冰糖"
}'
```

### 完整歌词示例

```bash
curl ... -d '{
  "input": "(唱歌)当你老了 头发白了 睡意昏沉[慢]当你老了 走不动了 炉火旁打盹 回忆青春",
  "voice": "冰糖"
}'
```

### 注意事项

- `(唱歌)` 必须在 input 的最开头
- 音色设计和语音克隆**不支持**唱歌模式
- 唱歌效果因音色而异——多试几个音色找到最合适的
- 可以在歌词中插入 `[标签]` 控制局部表现

---

## 方言与角色扮演

### 方言

```bash
curl ... -d '{"input": "(东北话)哎呀妈呀，你咋才来呢！"}'
curl ... -d '{"input": "(四川话)你啷个才来嘛，等到花儿都谢了。"}'
curl ... -d '{"input": "(河南话)今个天真冷啊，你穿厚点儿。"}'
curl ... -d '{"input": "(粤语)呢個真係好正啊！"}'
```

### 人设腔调 + 方言

```bash
curl ... -d '{"input": "(御姐音 慵懒)哦？就这？"}'
curl ... -d '{"input": "(正太音 开心)哥哥你看！我抓到蝴蝶了！"}'
curl ... -d '{"input": "(大叔音 磁沉)年轻人，做事要稳重些。"}'
curl ... -d '{"input": "(夹子音)拜托拜托～就帮我这一次嘛～"}'
```

### 角色扮演

```bash
# 孙悟空
curl ... -d '{"input": "(孙悟空)俺老孙来也！"}'

# 林黛玉
curl ... -d '{"input": "(林黛玉 惆怅)花谢花飞花满天，红消香断有谁怜。"}'
```

---

## 多风格融合 + 转场

一条长文本里实现多个风格的自然过渡：

```bash
# 从悲伤到坚定
curl ... -d '{
  "input": "(悲伤)我以为我会哭[哽咽]但是我没有。[深呼吸](坚定)我只是怔怔望着你的脚步，给你我最后的祝福。"
}'

# 从疑惑到愤怒
curl ... -d '{
  "input": "(疑惑)你说什么？[停顿](愤怒 冷漠)呵，我早该知道的。"
}'
```

支持**多粒度控制**：
- **段落级**：用 `(标签)` 切换整段基调
- **句子级**：用自然语言指令调节节奏
- **词级**：用 `[标签]` 精细控制局部

---

## 音色设计

用 `mimo-v2.5-tts-voicedesign` 模型，通过文本描述创造全新音色。

### 如何写好音色描述

| 维度 | 示例 |
|------|------|
| 性别与年龄 | "young woman in her mid-20s" |
| 音色质感 | "deep and gravelly"、"丝滑醇厚" |
| 情绪语气 | "warm and confident" |
| 语速节奏 | "slow and deliberate"、"语速极快，像连珠炮" |

### 完整示例

```bash
curl http://localhost:8080/v1/audio/speech \
  -H "Authorization: Bearer sk-mimo" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mimo-v2.5-tts-voicedesign",
    "input": "欢迎收听深夜电台，我是你的老朋友。",
    "style": "中年男性，声音低沉有磁性，语速缓慢，带着深夜的温暖和故事感"
  }' --output radio.wav
```

### 注意事项

- 1-4 句话即可，不需要太长
- 不要写矛盾的特征（"又年轻又苍老"）
- 不要写音效词（"带混响"、"加回声"）
- 合成的文本最好贴合音色描述中的角色

---

## 语音克隆

用 `mimo-v2.5-tts-voiceclone` 模型 + 音频样本（data URI）克隆任意声音。

### 准备工作

```bash
# 方式一：用自己的音频文件
BASE64=$(base64 -w0 my_voice.wav)

# 方式二：用自举法（先用 TTS 生成样本，再克隆）
curl -s http://localhost:8080/v1/audio/speech \
  -H "Authorization: Bearer sk-mimo" \
  -H "Content-Type: application/json" \
  -d '{"model":"mimo-v2.5-tts","input":"测试样本","voice":"冰糖"}' \
  --output ~/sample.wav
B64=$(base64 -w0 ~/sample.wav)

# 方式三：从 URL 下载音频
curl -sL "https://example.com/voice.wav" -o ~/voice.wav
B64=$(base64 -w0 ~/voice.wav)
```

### 克隆并合成

```bash
curl http://localhost:8080/v1/audio/speech \
  -H "Authorization: Bearer sk-mimo" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"mimo-v2.5-tts-voiceclone\",
    \"input\": \"这是克隆出来的声音，听起来像原声吗？\",
    \"voice\": \"data:audio/wav;base64,${B64}\"
  }" --output cloned.wav
```

### 调试技巧：自举法验证克隆效果

```bash
# 步骤1：用冰糖音色生成一句话
curl -s http://localhost:8080/v1/audio/speech \
  -H "Authorization: Bearer sk-mimo" \
  -H "Content-Type: application/json" \
  -d '{"model":"mimo-v2.5-tts","input":"你好，这是一个测试样本","voice":"冰糖"}' \
  -o ~/source.wav

# 步骤2：用这个样本做语音克隆
S64=$(base64 -w0 ~/source.wav)
curl -s http://localhost:8080/v1/audio/speech \
  -H "Authorization: Bearer sk-mimo" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"mimo-v2.5-tts-voiceclone\",\"input\":\"克隆出来的声音\",\"voice\":\"data:audio/wav;base64,${S64}\"}" \
  -o ~/result.wav

# 对比 source.wav 和 result.wav 听效果
```

### 限制

- Base64 音频 ≤ 10 MB
- 仅支持 wav 和 mp3 格式
- 不支持唱歌模式
- 生成时间较长（可达 300 秒），确保客户端不超时

---

## 常见场景配方

### 📖 有声小说

```bash
curl ... -d '{
  "input": "(深沉 磁性)夜幕降临，古老的城堡笼罩在薄雾之中[吸气]一阵冷风吹过，树叶沙沙作响。",
  "voice": "白桦"
}'
```

### 🗣️ 电台 / 播客

```bash
curl ... -d '{
  "input": "(温柔)听众朋友们晚上好，欢迎收听今晚的《城市夜话》。今晚我们来聊聊——孤独。",
  "voice": "茉莉",
  "speed": 0.9
}'
```

### 🎮 游戏角色

```bash
# 冷漠反派
curl ... -d '{
  "input": "(高冷 冷漠)你以为这样就结束了？[冷笑]太天真了。",
  "voice": "苏打"
}'

# 活泼萝莉
curl ... -d '{
  "input": "(俏皮 开心)嘿！冒险家！你终于来了！我等你好久了！",
  "voice": "冰糖"
}'
```

### 📢 广告 / 宣传

```bash
curl ... -d '{
  "input": "(磁性 干练)限时优惠，错过今天，再等一年！立即抢购！",
  "voice": "苏打",
  "speed": 1.2
}'
```

### 🎤 直播 / 解说

```bash
curl ... -d '{
  "input": "(激动 兴奋)球进了！！绝杀！！！三比二！中国队赢了！",
  "voice": "冰糖",
  "speed": 1.3
}'
```

### 💬 日常对话

```bash
# 撒娇
curl ... -d '{
  "input": "(委屈 撒娇)人家等了你这么久[撅嘴]你怎么才来呀～",
  "voice": "茉莉"
}'

# 生气
curl ... -d '{
  "input": "(愤怒)我说了多少次了！你怎么就是不听！",
  "voice": "冰糖"
}'
```

---

---

> **更多参考：** [官方语音合成文档](https://platform.xiaomimimo.com/docs/zh-CN/usage-guide/speech-synthesis-v2.5)
