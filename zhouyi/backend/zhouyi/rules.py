"""朱子变占选文规则，三爻变按原图二十项明序分前后。"""
VERSION='zhuzi-bianshi-1.0'
THREE_MOVING_ORDER=((1,2,3),(1,2,4),(1,2,5),(1,2,6),(1,3,4),(1,3,5),(1,3,6),(1,4,5),(1,4,6),(1,5,6),
                    (2,3,4),(2,3,5),(2,3,6),(2,4,5),(2,4,6),(2,5,6),(3,4,5),(3,4,6),(3,5,6),(4,5,6))

def select_passages(cast):
    moving=sorted(cast['moving']); n=len(moving)
    base,changed=cast['original_id'],cast['changed_id']
    def passage(h,kind='judgment',position=None): return {'hexagram_id':h,'kind':kind,'position':position}
    secondary=[]
    if n==0:
        primary=passage(base); reason='无变爻，以本卦卦辞为主。'
    elif n==1:
        primary=passage(base,'line',moving[0]); reason='一爻变，读本卦该变爻爻辞。'
    elif n==2:
        primary=passage(base,'line',moving[1]); secondary=[passage(base,'line',moving[0])]; reason='二爻变，读本卦两变爻，以上爻为主。'
    elif n==3:
        before=THREE_MOVING_ORDER.index(tuple(moving))<10
        primary=passage(base if before else changed); secondary=[passage(changed if before else base)]
        reason='三爻变，兼读本卦与之卦卦辞；原图二十项'+('前十项以本卦为主。' if before else '后十项以之卦为主。')
    elif n==4:
        still=[i for i in range(1,7) if i not in moving]
        primary=passage(changed,'line',still[0]); secondary=[passage(changed,'line',still[1])]; reason='四爻变，读之卦两不变爻，以下爻为主。'
    elif n==5:
        primary=passage(changed,'line',next(i for i in range(1,7) if i not in moving)); reason='五爻变，读之卦唯一不变爻。'
    elif n==6:
        primary=passage(base,'use') if base in (1,2) else passage(changed)
        reason='六爻全变，乾坤读用九或用六，其余读之卦卦辞。'
    else: raise ValueError('变爻数量须为 0 至 6')
    return {'version':VERSION,'reason':reason,'primary':[primary],'secondary':secondary}
