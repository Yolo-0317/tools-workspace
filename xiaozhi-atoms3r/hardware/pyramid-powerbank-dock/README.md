# Echo Pyramid 一体仓 + 阶梯平板盖

把 **AtomS3R + Echo Pyramid** 和竖放充电宝做成一套可 3D 打印的底座：Pyramid 坐左侧仓，充电宝坐右侧竖仓，短 Type-C 从共用壁穿孔连接。

## 结构一览

- Pyramid 仓：内净空约 **99×99 mm**，顶缘阶梯 + **分体平板盖**（前缘翘口）
- 电池仓：与 Pyramid 仓**顶齐平、共用一侧壁**；顶口敞开（宝可高出）；外侧约 80% 侧窗
- 支撑：Pyramid 侧一条圆弧薄脚；电池仓外壁通到地面
- 出音：仓底约 52×52 开口 + 离地脚；外侧壁有麦拾音口
- 无磁吸、无铰链

```text
俯视：

  ┌──────────────┬────┐
  │  Pyramid 仓  │ 电 │
  │  + 平板盖    │ 池 │  ← 共用壁，底部走线孔
  │              │ 仓 │
  └──────────────┴────┘
       圆弧条脚      通地支撑
```

## 文件是干什么的

| 文件 | 作用 |
|------|------|
| `dock.scad` | **参数化设计源文件**（OpenSCAD）。改尺寸、开口都在这里改，再导出模型。 |
| `dock_base.stl` | **底座的打印模型**（三角形网格）。交给切片软件（Cura / Bambu Studio / PrusaSlicer 等）切片后打底座。 |
| `dock_lid.stl` | **顶盖的打印模型**。同样拿去切片、打印盖子。 |
| `README.md` | 本说明。 |

**STL 是什么：**  
一种通用的 3D 模型交换格式，描述物体表面（很多小三角形）。打印机 / 切片软件认 STL，一般**不直接认** `.scad`。所以日常打印用的是两个 `.stl`；以后要改设计，改 `.scad` 再重新导出 STL。

导出命令（本机有 OpenSCAD 时）：

```bash
OPENSCAD="/Applications/OpenSCAD-2021.01.app/Contents/MacOS/OpenSCAD"
DIR="xiaozhi-atoms3r/hardware/pyramid-powerbank-dock"
"$OPENSCAD" -o "$DIR/dock_base.stl" -D 'part="base"' "$DIR/dock.scad"
"$OPENSCAD" -o "$DIR/dock_lid.stl"  -D 'part="lid"'  "$DIR/dock.scad"
```

## 推荐装配顺序

按「**Pyramid 先进仓，再接线**」来（手从底板开口 / 侧窗够得到插头即可）：

1. **放 Pyramid**  
   揭开平板盖，把 AtomS3R 已插好的 Pyramid 竖直放入左侧仓，坐稳在底板边框上。

2. **穿线接线**  
   - 建议用**短双弯头 Type-C**。  
   - 一头从共用壁底部开孔伸到 Pyramid 仓，插进 **Pyramid 底部 Type-C**（可从仓底大开口辅助对孔）。  
   - 另一头留在电池仓底部，口朝共用壁一侧。

3. **插充电宝**  
   充电宝竖着从电池仓**顶口**放入（可高出仓顶）；侧窗方便捏住调整。USB 口朝下、对着共用壁走线孔，接上刚才留好的插头。

4. **盖盖**  
   平板盖落入仓顶阶梯，前缘翘口方便下次打开。

拆：先拔充电宝（或先拔线）→ 开盖 → 取出 Pyramid。换电一般只用抽电池仓，不必动 Pyramid。

## 顶盖怎么卡

```text
外沿唇 rim_lip (~2.1)
    ┌──────────────┐
    │ ▢ 平板盖 ▢   │  ← 略小于座口，落在 step 上
────┴──阶梯 step──┴────
        内腔
```

前边外唇挖开一段，盖子前缘对应切口，指甲从这里翘起。

## 打印建议

- 材料：PLA / PETG；层高 0.2；壁 ≥3 圈；填充 20～30%
- 底座：底面朝下（脚在下）；盖子：平面朝下少支撑
- 若宝或 Pyramid 偏紧：加大 `pb_clear` 或 `chamber_inner` 后重导 STL

## 常用参数（`dock.scad`）

```openscad
chamber_inner = 99.0; // Pyramid 仓内净空
stack_h = 80.0;       // 仓内净高（盖下）
foot_h = 6.0;         // 条脚高度
foot_strip_w = 6.0;   // 条脚宽度
wall = 4.5;           // 壁厚
step = 2.4;           // 盖子阶梯宽
lid_t = 2.6;          // 盖厚
lid_clear = 0.5;      // 盖与座口间隙
pry_w = 24.0;         // 翘口宽度
pb_clear = 1.2;       // 电池仓每边间隙
cable_pass_h = 18.0;  // 共用壁走线孔高度
```

## 注意

- Pyramid 日常请从**底部 Type-C**供电（经充电宝）。  
- 满音量约 0.6 A，充电宝需能持续 5V≥1A；忌「小电流自动断电」的宝。  
