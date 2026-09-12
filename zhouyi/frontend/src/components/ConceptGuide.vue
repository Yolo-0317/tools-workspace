<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{
  kind: "hexagram" | "najia";
  moving?: number[];
}>();

const positionNames = ["初爻", "二爻", "三爻", "四爻", "五爻", "上爻"];
const movingText = computed(() => {
  const moving = props.moving || [];
  if (!moving.length) return "这次没有动爻，本卦与之卦相同，阅读时以本卦为主。";
  return `这次是${moving.map((position) => positionNames[position - 1]).join("、")}发生变化。`;
});
</script>

<template>
  <details
    v-if="kind === 'hexagram'"
    class="concept-guide"
    data-testid="hexagram-concept-guide"
  >
    <summary>概念百科：本卦、动爻与之卦</summary>
    <dl>
      <div>
        <dt>本卦</dt>
        <dd>本卦是六次随机结果直接组成的卦，用来呈现问题当下的基本结构和处境。</dd>
      </div>
      <div>
        <dt>动爻</dt>
        <dd>{{ movingText }}爻位从下往上数，最下面是初爻，最上面是上爻。</dd>
      </div>
      <div>
        <dt>之卦</dt>
        <dd>之卦由本卦的动爻阴阳翻转后形成，用来观察事情可能转向的状态，不是重新起了一卦。</dd>
      </div>
    </dl>
  </details>

  <details
    v-else
    class="concept-guide concept-guide-wide"
    data-testid="najia-concept-guide"
  >
    <summary>概念百科：什么是六爻纳甲盘</summary>
    <p class="concept-intro">
      六爻纳甲盘，是把本卦的六条爻、起卦时间和传统纳甲规则排成一张关系表。它不是生辰八字排盘，不需要姓名、性别或出生时间。
    </p>
    <dl>
      <div>
        <dt>纳甲</dt>
        <dd>按照卦与爻的位置，为每一爻配上天干、地支和五行，是后续判断各种关系的基础。</dd>
      </div>
      <div>
        <dt>世爻、应爻</dt>
        <dd>世爻通常作为提问者或自身处境的观察点；应爻通常观察对方、环境或所问之事的另一端。</dd>
      </div>
      <div>
        <dt>六亲</dt>
        <dd>根据每爻五行与本宫五行的生克关系，分为父母、兄弟、子孙、妻财、官鬼。它们是事物角色分类，不必只按亲属字面理解。</dd>
      </div>
      <div>
        <dt>六神</dt>
        <dd>按起卦日的天干依次排列的辅助符号，用来补充观察事物的表现方式，不能单独决定结果。</dd>
      </div>
      <div>
        <dt>旬空</dt>
        <dd>六十甲子的每一旬只有十组干支，会缺少两个地支；盘中将这两个地支标为空，作为传统规则中的状态标签。</dd>
      </div>
      <div>
        <dt>月日状态</dt>
        <dd>比较每爻地支与月建、日辰之间的生克、冲合等关系，用来观察哪些因素在当前时间较受支持或牵制。</dd>
      </div>
      <div>
        <dt>观察重点</dt>
        <dd>根据问题选择世爻、应爻或某类六亲作为主要阅读入口。它帮助组织解读，不代表只看这一项。</dd>
      </div>
    </dl>
  </details>
</template>
