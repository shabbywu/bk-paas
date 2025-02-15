<template lang="html">
  <div class="overview-content">
    <template v-if="isPluginFound">
      <div class="wrap">
        <div class="overview">
          <div
            class="overview-main"
            :style="{ 'min-height': routeNameMap.includes($route.name) ? '0px' : `${minHeight}px` }"
          >
            <div class="overview-fleft overview-fleft-plugin">
              <plugin-quick-nav ref="quickNav" />
              <div
                style="height: 100%;"
                @click="hideQuickNav"
              >
                <paas-plugin-nav />
              </div>
            </div>
            <div
              :class="['overview-fright-plugin', { 'hide-pd-bottom': $route.name === 'pluginVersionRelease' }]"
              @click="hideQuickNav"
            >
              <router-view
                v-if="userVisitEnable && pluginVisitEnable"
                :key="$route.path"
                class="right-main-plugin"
                @current-plugin-info-updated="pluginInfoUpdatedCallback"
              />

              <div
                v-else
                class="paas-loading-content"
              >
                <div class="no-permission">
                  <img src="/static/images/permissions.png">
                  <h2 v-if="errorMessage">
                    {{ errorMessage }}
                  </h2>
                  <h2
                    v-else-if="deniedMessageType === 'default'"
                    class="exception-text"
                  >
                    <div>
                      {{ $t('您没有访问当前应用该功能的权限，如需申请，请联系') }}
                      <router-link
                        class="toRolePage"
                        :to="{ name: 'pluginRoles', params: { pluginTypeId: pdId, id: pluginId } }"
                      >
                        {{ $t('成员管理') }}
                      </router-link>
                      {{ $t('页面的应用管理员') }}
                    </div>
                  </h2>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
    <template v-else>
      <div
        class="nofound"
        style="width: 1180px; margin: 0px auto;"
      >
        <img src="/static/images/404.png">
        <p> {{ $t('应用找不到了！') }} </p>
      </div>
    </template>
  </div>
</template>

<script>
    import paasPluginNav from '@/components/paas-plugin-nav';
    import pluginQuickNav from '@/components/plugin-quick-nav';
    import { bus } from '@/common/bus';
    import pluginBaseMixin from '@/mixins/plugin-base-mixin';
    import store from '@/store';

    // 当前路由页面不需要指定的min-height
    const ROUTE_NAME = ['pluginVersionRelease', 'marketInfoEdit'];

    export default {
        components: {
            paasPluginNav,
            pluginQuickNav
        },
        mixins: [pluginBaseMixin],
        data () {
            return {
                minHeight: 700,
                isPluginFound: true,
                navCategories: [],
                allNavItems: [],
                navItems: [],
                allowNavItems: [],
                pluginVisitEnable: true,
                userVisitEnable: true,
                errorMessage: '',
                deniedMessageType: 'default',
                showMarketMenus: true,
                // 非应用引擎 应用 时所要显示的父级导航
                parentNavIds: [8, 10],
                // 非应用引擎 应用 时所要显示的子级导航
                subNavIds: [10, 12, 13, 14],
                type: 'default',
                routeNameMap: ROUTE_NAME
            };
        },
        computed: {
            routeName () {
                return this.$route.name;
            }
        },
        watch: {
            '$route': {
                immediate: true,
                handler () {
                    this.userVisitEnable = true;
                    this.errorMessage = '';
                    this.checkPermission();
                }
            }
        },
        /**
         * 进入当前组件时请求应用信息
         */
        async beforeRouteEnter (to, from, next) {
            const pluginId = to.params.id; // 插件id
            const pluginTypeId = to.params.pluginTypeId; // 插件类型id

            try {
                // 是否获取应用信息, 复用开发者中心的页面需要获取应用信息
                if (to.meta.isGetAppInfo) {
                    await store.dispatch('plugin/getPluginAppInfo', { pluginId: pluginId, pdId: pluginTypeId });
                }
                if (!store.state.pluginInfo[pluginId]) {
                    await store.dispatch('plugin/getPluginInfo', { pluginId, pluginTypeId });
                }
                if (pluginId && pluginTypeId) {
                    const res = await store.dispatch('plugin/getPluginFeatureFlags', { pluginId: pluginId, pdId: pluginTypeId });
                    store.commit('plugin/updatePluginFeatureFlags', res);
                }
                next(true);
            } catch (e) {
                next({
                    name: 'plugin403',
                    params: {
                        id: pluginId,
                        pluginTypeId,
                        url: store.state.plugin.pluginApplyUrl
                    }
                });
            }
        },
        /**
         * 当前组件路由切换时请求应用信息
         */
        async beforeRouteUpdate (to, from, next) {
            const pluginId = to.params.id; // 插件id
            const pluginTypeId = to.params.pluginTypeId; // 插件类型id

            try {
                // 是否获取应用信息, 复用开发者中心的页面需要获取应用信息
                if (to.meta.isGetAppInfo) {
                    await store.dispatch('plugin/getPluginAppInfo', { pluginId: pluginId, pdId: pluginTypeId });
                }
                if (!store.state.pluginInfo[pluginId]) {
                    await store.dispatch('plugin/getPluginInfo', { pluginId, pluginTypeId });
                }
                if (pluginId && pluginTypeId) {
                    const res = await store.dispatch('plugin/getPluginFeatureFlags', { pluginId: pluginId, pdId: pluginTypeId });
                    store.commit('plugin/updatePluginFeatureFlags', res);
                }
                next(true);
            } catch (e) {
                next({
                    name: 'plugin403',
                    params: {
                        id: pluginId,
                        pluginTypeId,
                        url: store.state.plugin.pluginApplyUrl
                    }
                });
            }
        },
        async created () {
            bus.$on('api-error:user-permission-denied', () => {
                // 判定当前页面是应用内页
                // 当前应用无权限成员也可以访问应用首页 (屏蔽403时过滤应用首页)
                const RouterMatchedList = this.$route.matched;
                let capture = true;

                // undefined 为默认父级路由过滤设置
                if ((typeof RouterMatchedList[1].meta.capture403Error) !== 'undefined') {
                    capture = RouterMatchedList[1].meta.capture403Error;
                }
                if (capture) {
                    this.userVisitEnable = false;
                }
            });

            bus.$on('api-error:platform-fun-denied', (error) => {
                this.userVisitEnable = false;
                this.errorMessage = error.detail || this.$t('平台功能异常: 请联系平台负责人检查服务配置');
            });
            await this.initNavInfo();
        },
        mounted () {
            const HEADER_HEIGHT = 50;
            const FOOTER_HEIGHT = 0;
            const winHeight = window.innerHeight;
            const contentHeight = winHeight - HEADER_HEIGHT - FOOTER_HEIGHT;
            if (contentHeight > this.minHeight) {
                this.minHeight = contentHeight;
            }
            document.body.className = 'ps-app-detail';
        },
        beforeDestroy () {
            document.body.className = '';
        },
        methods: {
            async initNavInfo () {
              await this.$store.dispatch('plugin/getPluginInfo', { pluginId: this.pluginId, pluginTypeId: this.pdId });
            },
            async pluginInfoUpdatedCallback () {
                return await this.initNavInfo();
            },
            // 检查当前路由权限
            checkPermission () {
                // 应用是否有访问权限
                this.pluginVisitEnable = true;
            },
            hideQuickNav () {
                this.$refs.quickNav.hideSelectData();
            }
        }
    };
</script>

<style lang="scss" scoped>
    .no-permission {
        margin: 100px 30px 0 30px;
        font-size: 16px;
        text-align: center;

        h2 {
            margin-top: 15px;
            font-size: 14px;
            color: #666;
        }

        a {
            color: #3A84FF;
        }
    }

    .nofound {
        padding-top: 150px;
        width: 939px;
        text-align: center;
        font-size: 20px;
        color: #979797;
        line-height: 80px;
    }
    .hide-pd-bottom {
        padding-bottom: 0;
    }
</style>
