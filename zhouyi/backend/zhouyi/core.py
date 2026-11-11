"""三钱起卦；所有爻序、位串均自下而上。"""
import secrets

NAMES = '乾 坤 屯 蒙 需 訟 師 比 小畜 履 泰 否 同人 大有 謙 豫 隨 蠱 臨 觀 噬嗑 賁 剝 復 无妄 大畜 頤 大過 坎 離 咸 恆 遯 大壯 晉 明夷 家人 睽 蹇 解 損 益 夬 姤 萃 升 困 井 革 鼎 震 艮 漸 歸妹 豐 旅 巽 兌 渙 節 中孚 小過 既濟 未濟'.split()
# 下卦为行、上卦为列；八卦次序：乾兌離震巽坎艮坤。
TRIGRAMS = ('111','110','101','100','011','010','001','000')
KING_WEN = (
 (1,43,14,34,9,5,26,11),(10,58,38,54,61,60,41,19),
 (13,49,30,55,37,63,22,36),(25,17,21,51,42,3,27,24),
 (44,28,50,32,57,48,18,46),(6,47,64,40,59,29,4,7),
 (33,31,56,62,53,39,52,15),(12,45,35,16,20,8,23,2),
)
BITS_TO_ID = {low+high:KING_WEN[i][j] for i,low in enumerate(TRIGRAMS) for j,high in enumerate(TRIGRAMS)}
ID_TO_BITS = {v:k for k,v in BITS_TO_ID.items()}

def cast_coins():
    return [[secrets.choice((2,3)) for _ in range(3)] for _ in range(6)]

def describe_cast(coins):
    if not isinstance(coins,list) or len(coins)!=6 or any(
        not isinstance(row,list) or len(row)!=3 or any(type(v) is not int or v not in (2,3) for v in row) for row in coins
    ):
        raise ValueError('须按自下而上顺序提供六爻，每爻三个整数 2 或 3')
    values=[sum(row) for row in coins]
    original=''.join(str(v%2) for v in values)
    changed=''.join(str(1-v%2 if v in (6,9) else v%2) for v in values)
    return {'values':values,'moving':[i+1 for i,v in enumerate(values) if v in (6,9)],
            'original_bits':original,'changed_bits':changed,
            'original_id':BITS_TO_ID[original],'changed_id':BITS_TO_ID[changed]}
