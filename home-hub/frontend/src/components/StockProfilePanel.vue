<script setup lang="ts">
import { computed } from 'vue'
import {
  parseSelectionProfile,
  selCode,
  selIndustry,
  selName,
  splitCommaItems,
} from '../utils/selection'

const props = defineProps<{
  row: Record<string, unknown>
}>()

const profile = computed(() => parseSelectionProfile(props.row))
const code = computed(() => selCode(props.row))
const name = computed(() => selName(props.row))
const industry = computed(() => selIndustry(props.row))
const coreItems = computed(() => splitCommaItems(profile.value.coreCompetence))
const conceptPreview = computed(() => profile.value.conceptTags.slice(0, 16))
const conceptExtra = computed(() =>
  Math.max(0, profile.value.conceptTags.length - conceptPreview.value.length),
)
</script>

<template>
  <div class="profile-panel">
    <header class="profile-head">
      <div class="identity">
        <span class="name">{{ name }}</span>
        <span class="code">{{ code }}</span>
      </div>
      <span v-if="industry !== '—'" class="industry-badge">{{ industry }}</span>
    </header>

    <div v-if="profile.sectorPath.length || profile.region" class="sector-row">
      <nav v-if="profile.sectorPath.length" class="sector-path" aria-label="行业分类">
        <template v-for="(seg, i) in profile.sectorPath" :key="seg">
          <span class="path-seg">{{ seg }}</span>
          <span v-if="i < profile.sectorPath.length - 1" class="path-sep">›</span>
        </template>
      </nav>
      <span v-if="profile.region" class="region-tag">{{ profile.region }}</span>
    </div>

    <div v-if="conceptPreview.length" class="chip-row">
      <span v-for="tag in conceptPreview" :key="tag" class="chip">{{ tag }}</span>
      <span v-if="conceptExtra" class="chip muted">+{{ conceptExtra }}</span>
    </div>

    <div class="sections">
      <section v-if="profile.industryBackground" class="block">
        <h4>行业背景</h4>
        <p>{{ profile.industryBackground }}</p>
      </section>

      <section v-if="coreItems.length" class="block">
        <h4>核心竞争力</h4>
        <ul class="bullet-list">
          <li v-for="item in coreItems" :key="item">{{ item }}</li>
        </ul>
      </section>

      <section v-if="profile.selectionReason" class="block highlight">
        <h4>入选理由</h4>
        <p>{{ profile.selectionReason }}</p>
      </section>

      <section v-if="profile.mainBusiness" class="block">
        <h4>主营业务</h4>
        <p>{{ profile.mainBusiness }}</p>
      </section>

      <section v-if="profile.businessScope" class="block">
        <h4>经营范围</h4>
        <p class="muted-text">{{ profile.businessScope }}</p>
      </section>
    </div>

    <p v-if="!profile.hasContent" class="empty">暂无档案数据</p>
  </div>
</template>

<style scoped>
.profile-panel {
  padding: 14px 16px;
  border-radius: 10px;
  background: linear-gradient(145deg, #111820 0%, #0d1218 100%);
  border: 1px solid #2a3548;
}

.profile-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.identity {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
}

.name {
  font-size: 16px;
  font-weight: 600;
  color: #f0f4fa;
}

.code {
  font-size: 12px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  color: #7d8da6;
  letter-spacing: 0.04em;
}

.industry-badge {
  flex-shrink: 0;
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 999px;
  background: #152238;
  color: #93c5fd;
  border: 1px solid #2a4060;
}

.sector-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 12px;
  margin-bottom: 12px;
}

.sector-path {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
  font-size: 13px;
  color: #b8c5d9;
}

.path-seg {
  padding: 2px 8px;
  border-radius: 6px;
  background: #161e2a;
}

.path-sep {
  color: #4b5c73;
  font-size: 11px;
}

.region-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 6px;
  background: #1a2420;
  color: #7dffb2;
}

.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 14px;
}

.chip {
  font-size: 11px;
  line-height: 1.4;
  padding: 3px 8px;
  border-radius: 999px;
  background: #1a2230;
  color: #c5d0e0;
  border: 1px solid #2a3548;
}

.chip.muted {
  color: #8b9cb3;
  background: transparent;
  border-style: dashed;
}

.sections {
  display: grid;
  gap: 12px;
}

.block {
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.22);
  border: 1px solid #1e2836;
}

.block.highlight {
  border-color: #2a4060;
  background: rgba(21, 34, 56, 0.45);
}

.block h4 {
  margin: 0 0 6px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #7d8da6;
}

.block p {
  margin: 0;
  font-size: 13px;
  line-height: 1.65;
  color: #dbe7ff;
}

.muted-text {
  color: #a8b8cc !important;
  font-size: 12px !important;
}

.bullet-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 4px;
}

.bullet-list li {
  position: relative;
  padding-left: 14px;
  font-size: 13px;
  line-height: 1.55;
  color: #dbe7ff;
}

.bullet-list li::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0.62em;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #60a5fa;
}

.empty {
  margin: 0;
  font-size: 13px;
  color: #8b9cb3;
}

@media (max-width: 768px) {
  .profile-panel {
    padding: 12px;
    border-radius: 8px;
  }

  .name {
    font-size: 15px;
  }

  .chip-row {
    gap: 5px;
  }

  .chip {
    font-size: 10px;
  }

  .block p,
  .bullet-list li {
    font-size: 12px;
  }
}
</style>
