<template>
  <div class="paas-empty-dark">
    <template v-if="!keyword">
      <img src="/static/images/empty-dark.png">
      <p class="empty-tips">
        {{ emptyTitle }}
      </p>
    </template>
    <template v-else>
      <img src="/static/images/search-empty.png">
      <div class="empty-tips">
        <p>{{ $t('搜索结果为空') }}</p>
        <div class="search-empty-tips">
          {{ $t('可以尝试 调整关键词 或') }}
          <span
            class="clear-search"
            @click="handlerClearFilter"
          >
            {{ $t('清空搜索条件') }}
          </span>
        </div>
      </div>
    </template>
  </div>
</template>

<script>
    import i18n from '@/language/i18n';
    export default {
        props: {
            keyword: {
                type: String,
                default: ''
            },
            // 暂无数据
            emptyTitle: {
                type: String,
                default: i18n.t('暂无数据')
            },
            // 是否为异常
            abnormal: {
                type: Boolean,
                default: false
            }
        },
        methods: {
            handlerClearFilter () {
                this.$emit('clear-filter');
            },
            toRefresh () {
                this.$emit('clear-filter');
                this.$emit('reacquire');
            }
        }
    };
</script>

<style lang="scss" scoped>
  .paas-empty-dark {
      text-align: center;
      .empty-tips {
          font-size: 14px;
          color: #979BA5;
      }
      .search-empty-tips {
          font-size: 12px;
          .clear-search {
              color: #699DF4;
              cursor: pointer;
          }
      }
  }
</style>
