<template lang="html">
  <div class="right-main">
    <app-top-bar
      v-if="isEngineEnabled"
      :title="$t('网站访问统计')"
      :can-create="canCreateModule"
      :cur-module="curAppModule"
      :module-list="curAppModuleList"
    />
    <div
      v-else
      class="ps-top-bar"
    >
      <h2> {{ $t('网站访问统计') }} </h2>
    </div>

    <paas-content-loader
      :is-loading="isLoading"
      placeholder="analysis-loading"
      :offset-top="20"
      class="app-container middle web-container"
    >
      <app-analysis
        :backend-type="'user_tracker'"
        tab-name="webAnalysis"
        :engine-enabled="isEngineEnabled"
        @data-ready="handleDataReady"
      />
    </paas-content-loader>
  </div>
</template>

<script>
import appBaseMixin from '@/mixins/app-base-mixin';
import appTopBar from '@/components/paas-app-bar';
import analysis from './comps/analysis';

export default {
  components: {
    appTopBar,
    appAnalysis: analysis,
  },
  mixins: [appBaseMixin],
  data() {
    return {
      isEngineEnabled: true,
      isLoading: true,
    };
  },
  watch: {
    '$route'() {
      this.isEngineEnabled = this.curAppInfo.web_config.engine_enabled;
      this.isLoading = true;
    },
  },
  created() {
    this.isEngineEnabled = this.curAppInfo.web_config.engine_enabled;
  },
  methods: {
    handleDataReady() {
      this.isLoading = false;
    },
  },
};
</script>
<style scoped lang="scss">
.web-container{
  background: #fff;
  margin: 16px auto 30px;
  padding: 1px 24px;
  width: calc(100% - 50px);
}
</style>
