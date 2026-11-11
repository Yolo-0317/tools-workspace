# 小苏打吹气球动画制作计划

**Goal:** 交付19幕、16:9、栀夏穿越讲解的无声视频。

**Architecture:** 已有栀夏透明帧、新厨房背景与Canvas解释对象独立合成；绝对时间求值控制反应、气泡、气体碰撞与转场，复用本地Playwright/FFmpeg渲染器。每句正文对应解释单元，实际配音后可延展。

**Tech Stack:** HTML/Canvas、huashu MO/CAM库、Python、Playwright、FFmpeg、内置imagegen。

## 约束

1920×1080、30fps、H.264；无音轨；栀夏全程；385字正文不删改；底部字幕无标点无遮罩；无清水对照、无瓶盖提醒。微观原子守恒，CO2线性结构，H2O折线结构，碳酸的H连接O；醋酸钠保留水相。

## 执行步骤

- [x] 复用角色并生成空厨房背景；素材只存本集，字体与上游代码保留许可。
- [x] qa/verify_timeline.cjs检查19句文本覆盖、时间连续与字幕无标点；engine/timeline.json按19句建立字幕与时长。
- [x] engine/chemistry.js输出reactionAtoms(q)，q=0为H2CO3，q=1为CO2+H2O，六个原子保持身份；bounce(t,v,size)计算连续反射轨迹。先用Node测试元素数量和撞壁连续性，再写函数。
- [x] engine/main.js集中处理瓶子、球囊、粒子、环境与19个场景key、镜头、转场、栀夏、字幕。
- [x] render.py先输出全部关键状态与转场接触表，检查角色、字幕、分子与场景边界；再导出完整无声视频。
- [x] 完整解码和流参数检查；冷/热渲染像素差、19幕连续采样帧差、字幕宽度与分子位置检查；独立审片挑实质问题，修正后只复测受影响项。

## 文件接口

window.prepare(t)、renderFrame(t)、__ready、__total、__canvas与已复用渲染器一致。chemistry.js可同时在浏览器与Node读取，用于验证原子身份与运动。qa保留截图、动画数据检查和实际成片属性，技术通过不能写成完整人工观看通过。
