<template>
  <div class="space-y-8">
    <section v-if="isLoading" class="rounded-3xl border border-border bg-card p-6 text-sm text-muted-foreground">
      正在加载设置...
    </section>

    <section v-else-if="loadError" class="rounded-3xl border border-destructive bg-destructive/10 p-6">
      <p class="text-base font-semibold text-destructive">加载设置失败</p>
      <p class="mt-2 text-sm text-destructive/80">{{ loadError }}</p>
      <button
        class="mt-4 rounded-full bg-destructive px-4 py-2 text-sm font-medium text-destructive-foreground transition-opacity hover:opacity-90"
        @click="settingsStore.loadSettings()"
      >
        重试
      </button>
    </section>

    <section v-else class="rounded-3xl border border-border bg-card p-6">
      <div class="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p class="text-base font-semibold text-foreground">配置面板</p>
          <p class="mt-1 text-xs text-muted-foreground">保存后立即生效，请留意右上角状态提示。</p>
        </div>
        <button
          class="rounded-full bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity
                 hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          :disabled="isSaving || !localSettings"
          @click="handleSave"
        >
          保存设置
        </button>
      </div>

      <div v-if="errorMessage" class="mt-4 rounded-2xl bg-destructive/10 px-4 py-3 text-sm text-destructive">
        {{ errorMessage }}
      </div>

      <div v-if="localSettings" class="mt-6 space-y-8">
        <div class="grid gap-6 lg:grid-cols-3">
          <div class="space-y-6">
            <div class="rounded-2xl border border-border bg-card p-5">
              <div>
                <p class="text-sm font-semibold text-foreground">基础与代理</p>
                <p class="mt-1 text-xs text-muted-foreground">API 与网络代理配置</p>
              </div>
              <div class="mt-5 space-y-4">
                <div class="space-y-2">
                  <label for="basic-api-key" class="block text-xs text-muted-foreground">API 密钥</label>
                  <input
                    id="basic-api-key"
                    v-model="localSettings.basic.api_key"
                    type="text"
                    class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                    placeholder="可选"
                  />
                </div>
                <div class="space-y-2">
                  <label for="basic-base-url" class="block text-xs text-muted-foreground">基础地址</label>
                  <input
                    id="basic-base-url"
                    v-model="localSettings.basic.base_url"
                    type="text"
                    class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                    placeholder="自动检测或手动填写"
                  />
                </div>
                <div class="space-y-2">
                  <div class="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                    <label for="basic-proxy-auth">账户操作代理</label>
                    <HelpTip text="用于注册/登录/刷新操作的代理，留空则禁用" />
                  </div>
                  <input
                    id="basic-proxy-auth"
                    v-model="localSettings.basic.proxy_for_auth"
                    type="text"
                    class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                    placeholder="http://127.0.0.1:7890"
                  />
                </div>
                <div class="space-y-2">
                  <div class="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                    <label for="basic-proxy-chat">聊天操作代理</label>
                    <HelpTip text="用于 JWT/会话/消息操作的代理，留空则禁用" />
                  </div>
                  <input
                    id="basic-proxy-chat"
                    v-model="localSettings.basic.proxy_for_chat"
                    type="text"
                    class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                    placeholder="http://127.0.0.1:7890"
                  />
                </div>
              </div>
            </div>

            <div class="rounded-2xl border border-border bg-card p-5">
              <div>
                <p class="text-sm font-semibold text-foreground">邮箱服务与注册</p>
                <p class="mt-1 text-xs text-muted-foreground">邮箱来源、注册配置与验证策略</p>
              </div>
              <div class="mt-5 space-y-6">
                <div class="space-y-3">
                  <div class="grid grid-cols-2 items-center gap-x-6 gap-y-2">
                    <Checkbox v-model="localSettings.basic.duckmail_verify_ssl">
                      DuckMail SSL 校验
                    </Checkbox>
                    <div class="flex items-center justify-end gap-2">
                      <Checkbox v-model="localSettings.basic.gptmail_verify_ssl">
                        GPTMail SSL 校验
                      </Checkbox>
                    </div>
                    <Checkbox v-model="localSettings.basic.moemail_verify_ssl">
                      MoeMail SSL 校验
                    </Checkbox>
                    <div class="flex items-center justify-end gap-2">
                      <Checkbox v-model="localSettings.basic.browser_headless">
                        无头浏览器
                      </Checkbox>
                      <HelpTip text="无头模式适用于服务器环境（如 Docker）。若注册/刷新失败，建议关闭。" />
                    </div>
                  </div>
                  <div class="space-y-2">
                    <div class="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                      <label for="basic-browser-engine">浏览器引擎</label>
                      <HelpTip text="UC: 支持无头/有头，但可能失败。DP: 支持无头/有头，更稳定，推荐使用。" />
                    </div>
                    <SelectMenu
                      id="basic-browser-engine"
                      v-model="localSettings.basic.browser_engine"
                      :options="browserEngineOptions"
                      aria-label="浏览器引擎"
                      class="w-full"
                    />
                  </div>
                </div>
                <div class="border-t border-border/60 pt-4 space-y-4">
                  <p class="text-xs font-medium text-foreground">邮箱服务配置</p>
                  <div class="grid gap-3 md:grid-cols-2">
                    <div class="space-y-2">
                      <label for="duckmail-base-url" class="block text-xs text-muted-foreground">DuckMail API 地址</label>
                      <input
                        id="duckmail-base-url"
                        v-model="localSettings.basic.duckmail_base_url"
                        type="text"
                        class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                        placeholder="https://api.duckmail.sbs"
                      />
                    </div>
                    <div class="space-y-2">
                      <label for="duckmail-api-key" class="block text-xs text-muted-foreground">DuckMail API Key</label>
                      <input
                        id="duckmail-api-key"
                        v-model="localSettings.basic.duckmail_api_key"
                        type="text"
                        class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                        placeholder="dk_xxx"
                      />
                    </div>
                  </div>
                  <div class="grid gap-3 md:grid-cols-2">
                    <div class="space-y-2">
                      <label for="gptmail-base-url" class="block text-xs text-muted-foreground">GPTMail API 地址</label>
                      <input
                        id="gptmail-base-url"
                        v-model="localSettings.basic.gptmail_base_url"
                        type="text"
                        class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                        placeholder="https://mail.chatgpt.org.uk"
                      />
                    </div>
                    <div class="space-y-2">
                      <label for="gptmail-api-key" class="block text-xs text-muted-foreground">GPTMail API Key</label>
                      <input
                        id="gptmail-api-key"
                        v-model="localSettings.basic.gptmail_api_key"
                        type="text"
                        class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                        placeholder="gpt-test"
                      />
                    </div>
                  </div>
                  <div class="grid gap-3 md:grid-cols-2">
                    <div class="space-y-2">
                      <label for="moemail-base-url" class="block text-xs text-muted-foreground">MoeMail API 地址</label>
                      <input
                        id="moemail-base-url"
                        v-model="localSettings.basic.moemail_base_url"
                        type="text"
                        class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                        placeholder="https://mail.ishalumi.me"
                      />
                    </div>
                    <div class="space-y-2">
                      <label for="moemail-api-key" class="block text-xs text-muted-foreground">MoeMail API Key</label>
                      <input
                        id="moemail-api-key"
                        v-model="localSettings.basic.moemail_api_key"
                        type="text"
                        class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                        placeholder="mk_xxx"
                      />
                    </div>
                  </div>
                  <div class="space-y-2">
                    <div class="flex items-center justify-between gap-2">
                      <label for="moemail-domain" class="block text-xs text-muted-foreground">MoeMail 邮箱域名</label>
                      <HelpTip text="支持多个域名，用逗号分隔，注册时随机选取" />
                    </div>
                    <input
                      id="moemail-domain"
                      v-model="localSettings.basic.moemail_domain"
                      type="text"
                      class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                      placeholder="a.com, b.com, c.com"
                    />
                  </div>
                </div>
                <div class="border-t border-border/60 pt-4 space-y-4">
                  <p class="text-xs font-medium text-foreground">注册与刷新</p>
                  <div class="space-y-2">
                    <div class="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                      <label for="register-provider">注册邮箱服务商</label>
                      <HelpTip text="注册时使用的邮箱来源" />
                    </div>
                    <SelectMenu
                      id="register-provider"
                      v-model="localSettings.basic.register_mail_provider"
                      :options="mailProviderOptions"
                      aria-label="注册邮箱服务商"
                      class="w-full"
                    />
                  </div>
                  <div class="grid gap-3 md:grid-cols-2">
                    <div class="space-y-2">
                      <label for="register-prefix" class="block text-xs text-muted-foreground">注册邮箱前缀（可选）</label>
                      <input
                        id="register-prefix"
                        v-model="localSettings.basic.register_mail_prefix"
                        type="text"
                        class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                        placeholder="myname"
                      />
                    </div>
                    <div class="space-y-2">
                      <label for="register-count" class="block text-xs text-muted-foreground">默认注册数量</label>
                      <input
                        id="register-count"
                        v-model.number="localSettings.basic.register_default_count"
                        type="number"
                        min="1"
                        class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                      />
                    </div>
                  </div>
                  <div class="grid gap-3 md:grid-cols-2">
                    <div class="space-y-2">
                      <label for="register-domain" class="block text-xs text-muted-foreground">默认注册域名（推荐）</label>
                      <input
                        id="register-domain"
                        v-model="localSettings.basic.register_domain"
                        type="text"
                        class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                        placeholder="留空则自动选择"
                      />
                    </div>
                    <div class="space-y-2">
                      <div class="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                        <label for="refresh-window-hours">过期刷新窗口（小时）</label>
                        <HelpTip text="当账号距离过期小于等于该值时，会触发自动登录刷新（更新 cookie/session）。" />
                      </div>
                      <input
                        id="refresh-window-hours"
                        v-model.number="localSettings.basic.refresh_window_hours"
                        type="number"
                        min="0"
                        class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div class="rounded-2xl border border-border bg-card p-5">
              <div>
                <p class="text-sm font-semibold text-foreground">自动化反检测</p>
                <p class="mt-1 text-xs text-muted-foreground">降低自动化特征暴露风险</p>
              </div>
              <div class="mt-5 space-y-6">
                <div class="grid grid-cols-2 items-center gap-x-6 gap-y-2">
                  <Checkbox v-model="localSettings.automation.stealth_enabled">
                    启用反检测脚本
                  </Checkbox>
                  <div class="flex items-center justify-end gap-2">
                    <Checkbox v-model="localSettings.automation.webrtc_protect">
                      禁用 WebRTC 泄露
                    </Checkbox>
                    <HelpTip text="强制 WebRTC 走代理，避免本机 IP 泄露" />
                  </div>
                </div>
                <div class="border-t border-border/60 pt-4 space-y-4">
                  <p class="text-xs font-medium text-foreground">指纹与位置</p>
                  <div class="space-y-2">
                    <div class="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                      <label for="automation-timezone">浏览器时区</label>
                      <HelpTip text="留空表示不覆盖，例如 America/Los_Angeles" />
                    </div>
                    <input
                      id="automation-timezone"
                      v-model="localSettings.automation.timezone"
                      type="text"
                      class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                      placeholder="America/Los_Angeles"
                    />
                  </div>
                  <div class="space-y-2">
                    <div class="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                      <label for="automation-geo-lat">地理位置（可选）</label>
                      <HelpTip text="需同时填写经纬度，精度单位为米" />
                    </div>
                    <div class="grid grid-cols-2 gap-3">
                      <input
                        id="automation-geo-lat"
                        v-model.number="localSettings.automation.geo_latitude"
                        type="number"
                        step="0.0001"
                        class="rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                        placeholder="纬度"
                      />
                      <input
                        id="automation-geo-lng"
                        v-model.number="localSettings.automation.geo_longitude"
                        type="number"
                        step="0.0001"
                        class="rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                        placeholder="经度"
                      />
                      <input
                        id="automation-geo-accuracy"
                        v-model.number="localSettings.automation.geo_accuracy"
                        type="number"
                        min="1"
                        class="col-span-2 rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                        placeholder="精度（米），如 50"
                      />
                    </div>
                  </div>
                </div>
                <div class="border-t border-border/60 pt-4 space-y-4">
                  <p class="text-xs font-medium text-foreground">随机延迟</p>
                  <div class="space-y-2">
                    <div class="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                      <label for="automation-random-delay-min">随机延迟（毫秒）</label>
                      <HelpTip text="用于点击/跳转等操作的随机等待区间" />
                    </div>
                    <div class="grid grid-cols-2 gap-3">
                      <input
                        id="automation-random-delay-min"
                        v-model.number="localSettings.automation.random_delay_min_ms"
                        type="number"
                        min="0"
                        class="rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                        placeholder="最小值"
                      />
                      <input
                        id="automation-random-delay-max"
                        v-model.number="localSettings.automation.random_delay_max_ms"
                        type="number"
                        min="0"
                        class="rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                        placeholder="最大值"
                      />
                    </div>
                  </div>
                  <div class="space-y-2">
                    <div class="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                      <label for="automation-between-account-min">注册账号间隔（秒）</label>
                      <HelpTip text="批量注册时每个账号之间的随机等待区间" />
                    </div>
                    <div class="grid grid-cols-2 gap-3">
                      <input
                        id="automation-between-account-min"
                        v-model.number="localSettings.automation.between_account_min_seconds"
                        type="number"
                        min="0"
                        class="rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                        placeholder="最小值"
                      />
                      <input
                        id="automation-between-account-max"
                        v-model.number="localSettings.automation.between_account_max_seconds"
                        type="number"
                        min="0"
                        class="rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                        placeholder="最大值"
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>

          </div>

          <div class="space-y-6">
            <div class="rounded-2xl border border-border bg-card p-5">
              <div>
                <p class="text-sm font-semibold text-foreground">重试与会话</p>
                <p class="mt-1 text-xs text-muted-foreground">失败恢复与会话生命周期</p>
              </div>
              <div class="mt-5 space-y-6 text-sm">
                <div class="space-y-3">
                  <p class="text-xs font-medium text-foreground">重试策略</p>
                  <div class="grid gap-3 sm:grid-cols-2">
                    <div class="space-y-2">
                      <label for="retry-new-session-tries" class="text-xs text-muted-foreground">新会话尝试次数</label>
                      <input
                        id="retry-new-session-tries"
                        v-model.number="localSettings.retry.max_new_session_tries"
                        type="number"
                        min="1"
                        class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                      />
                    </div>
                    <div class="space-y-2">
                      <label for="retry-request-retries" class="text-xs text-muted-foreground">请求重试次数</label>
                      <input
                        id="retry-request-retries"
                        v-model.number="localSettings.retry.max_request_retries"
                        type="number"
                        min="0"
                        class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                      />
                    </div>
                    <div class="space-y-2">
                      <label for="retry-stream-auto-retry" class="text-xs text-muted-foreground">流式不完整重试次数</label>
                      <input
                        id="retry-stream-auto-retry"
                        v-model.number="localSettings.retry.stream_auto_retry_times"
                        type="number"
                        min="0"
                        max="5"
                        class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                      />
                    </div>
                    <div class="space-y-2">
                      <label for="retry-account-switch-tries" class="text-xs text-muted-foreground">账号切换次数</label>
                      <input
                        id="retry-account-switch-tries"
                        v-model.number="localSettings.retry.max_account_switch_tries"
                        type="number"
                        min="1"
                        class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                      />
                    </div>
                    <div class="space-y-2">
                      <label for="retry-failure-threshold" class="text-xs text-muted-foreground">失败阈值</label>
                      <input
                        id="retry-failure-threshold"
                        v-model.number="localSettings.retry.account_failure_threshold"
                        type="number"
                        min="1"
                        class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                      />
                    </div>
                    <div class="space-y-2 sm:col-span-2">
                      <label for="retry-rate-limit-cooldown" class="text-xs text-muted-foreground">限流冷却（分钟）</label>
                      <input
                        id="retry-rate-limit-cooldown"
                        v-model.number="rateLimitCooldownMinutes"
                        type="number"
                        min="1"
                        max="720"
                        step="1"
                        class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                      />
                    </div>
                  </div>
                </div>
                <div class="border-t border-border/60 pt-4 space-y-3">
                  <p class="text-xs font-medium text-foreground">会话与缓存</p>
                  <div class="grid gap-3 sm:grid-cols-2">
                    <div class="space-y-2">
                      <label for="retry-session-cache-ttl" class="text-xs text-muted-foreground">会话缓存秒数</label>
                      <input
                        id="retry-session-cache-ttl"
                        v-model.number="localSettings.retry.session_cache_ttl_seconds"
                        type="number"
                        min="0"
                        class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                      />
                    </div>
                    <div class="space-y-2">
                      <label for="session-expire-hours" class="text-xs text-muted-foreground">会话有效时长（小时）</label>
                      <input
                        id="session-expire-hours"
                        v-model.number="localSettings.session.expire_hours"
                        type="number"
                        min="1"
                        class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                      />
                    </div>
                    <div class="space-y-2 sm:col-span-2">
                      <div class="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                        <label for="retry-auto-refresh-accounts">自动刷新账号间隔（秒，0禁用）</label>
                        <HelpTip text="仅在数据库存储启用时生效：用于检测账号配置变化并重载列表，不会刷新 cookie。文件存储模式不会触发。" />
                      </div>
                      <input
                        id="retry-auto-refresh-accounts"
                        v-model.number="localSettings.retry.auto_refresh_accounts_seconds"
                        type="number"
                        min="0"
                        max="600"
                        class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="space-y-6">
            <div class="rounded-2xl border border-border bg-card p-5">
              <div>
                <p class="text-sm font-semibold text-foreground">图像生成</p>
                <p class="mt-1 text-xs text-muted-foreground">文生图模型与输出格式</p>
              </div>
              <div class="mt-5 space-y-4">
                <Checkbox v-model="localSettings.image_generation.enabled">
                  启用图像生成
                </Checkbox>
                <div class="space-y-2">
                  <label for="image-output-format" class="block text-xs text-muted-foreground">输出格式</label>
                  <SelectMenu
                    id="image-output-format"
                    v-model="localSettings.image_generation.output_format"
                    :options="imageOutputOptions"
                    aria-label="图像输出格式"
                    placement="up"
                    class="w-full"
                  />
                </div>
                <div class="space-y-2">
                  <label for="image-supported-models" class="block text-xs text-muted-foreground">支持模型</label>
                  <SelectMenu
                    id="image-supported-models"
                    v-model="localSettings.image_generation.supported_models"
                    :options="imageModelOptions"
                    aria-label="图像支持模型"
                    placeholder="选择模型"
                    placement="up"
                    multiple
                    class="w-full"
                  />
                </div>
              </div>
            </div>

            <div class="rounded-2xl border border-border bg-card p-5">
              <div>
                <p class="text-sm font-semibold text-foreground">视频生成</p>
                <p class="mt-1 text-xs text-muted-foreground">使用 gemini-veo 模型时生效</p>
              </div>
              <div class="mt-5 space-y-2">
                <label for="video-output-format" class="block text-xs text-muted-foreground">输出格式</label>
                <SelectMenu
                  id="video-output-format"
                  v-model="localSettings.video_generation.output_format"
                  :options="videoOutputOptions"
                  aria-label="视频输出格式"
                  placement="up"
                  class="w-full"
                />
              </div>
            </div>

            <div class="rounded-2xl border border-border bg-card p-5">
              <div>
                <p class="text-sm font-semibold text-foreground">公开展示</p>
                <p class="mt-1 text-xs text-muted-foreground">Logo 与入口配置</p>
              </div>
              <div class="mt-5 space-y-4">
                <div class="space-y-2">
                  <label for="public-logo-url" class="block text-xs text-muted-foreground">Logo 地址</label>
                  <input
                    id="public-logo-url"
                    v-model="localSettings.public_display.logo_url"
                    type="text"
                    class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                    placeholder="logo 地址"
                  />
                </div>
                <div class="space-y-2">
                  <label for="public-chat-url" class="block text-xs text-muted-foreground">聊天入口</label>
                  <input
                    id="public-chat-url"
                    v-model="localSettings.public_display.chat_url"
                    type="text"
                    class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                    placeholder="聊天入口地址"
                  />
                </div>
              </div>
            </div>

            <div class="rounded-2xl border border-border bg-card p-5">
              <p class="text-sm font-semibold text-foreground">说明</p>
              <div class="mt-4 space-y-2 text-sm text-muted-foreground">
                <p>保存后会直接写入配置文件并热更新。</p>
                <p>自动注册/刷新若依赖缺失会自动降级并提示。</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useSettingsStore } from '@/stores/settings'
import { useToast } from '@/composables/useToast'
import SelectMenu from '@/components/ui/SelectMenu.vue'
import Checkbox from '@/components/ui/Checkbox.vue'
import HelpTip from '@/components/ui/HelpTip.vue'
import type { Settings } from '@/types/api'

const settingsStore = useSettingsStore()
const { settings, isLoading, loadError } = storeToRefs(settingsStore)
const toast = useToast()

const localSettings = ref<Settings | null>(null)
const isSaving = ref(false)
const errorMessage = ref('')

// 429冷却时间：分钟 ↔ 秒 的转换
const rateLimitCooldownMinutes = computed({
  get: () => {
    if (!localSettings.value?.retry?.rate_limit_cooldown_seconds) return 1
    const seconds = localSettings.value.retry.rate_limit_cooldown_seconds
    const minutes = Math.round(seconds / 60)
    return minutes < 1 || minutes > 720 ? 1 : minutes
  },
  set: (minutes: number) => {
    if (localSettings.value?.retry) {
      localSettings.value.retry.rate_limit_cooldown_seconds = minutes * 60
    }
  }
})

const browserEngineOptions = [
  { label: 'UC - 支持无头/有头', value: 'uc' },
  { label: 'DP - 支持无头/有头（推荐）', value: 'dp' },
]
const mailProviderOptions = [
  { label: 'DuckMail', value: 'duckmail' },
  { label: 'GPTMail', value: 'gptmail' },
  { label: 'MoeMail', value: 'moemail' },
]
const imageOutputOptions = [
  { label: 'Base64 编码', value: 'base64' },
  { label: 'URL 链接', value: 'url' },
]
const videoOutputOptions = [
  { label: 'HTML 视频标签', value: 'html' },
  { label: 'URL 链接', value: 'url' },
  { label: 'Markdown 格式', value: 'markdown' },
]
const imageModelOptions = computed(() => {
  const baseOptions = [
    { label: 'Gemini 3 Pro Preview', value: 'gemini-3-pro-preview' },
    { label: 'Gemini 3 Flash Preview', value: 'gemini-3-flash-preview' },
    { label: 'Gemini 2.5 Pro', value: 'gemini-2.5-pro' },
    { label: 'Gemini 2.5 Flash', value: 'gemini-2.5-flash' },
    { label: 'Gemini Auto', value: 'gemini-auto' },
  ]

  const selected = localSettings.value?.image_generation.supported_models || []
  for (const value of selected) {
    if (!baseOptions.some(option => option.value === value)) {
      baseOptions.push({ label: value, value })
    }
  }

  return baseOptions
})

watch(settings, (value) => {
  if (!value) return
  const next = JSON.parse(JSON.stringify(value))
  next.image_generation = next.image_generation || { enabled: false, supported_models: [], output_format: 'base64' }
  next.image_generation.output_format ||= 'base64'
  next.video_generation = next.video_generation || { output_format: 'html' }
  next.video_generation.output_format ||= 'html'
  next.basic = next.basic || {}
  next.basic.duckmail_base_url ||= 'https://api.duckmail.sbs'
  next.basic.duckmail_verify_ssl = next.basic.duckmail_verify_ssl ?? true
  next.basic.gptmail_verify_ssl = next.basic.gptmail_verify_ssl ?? true
  next.basic.moemail_verify_ssl = next.basic.moemail_verify_ssl ?? true
  next.basic.browser_engine = next.basic.browser_engine || 'dp'
  next.basic.browser_headless = next.basic.browser_headless ?? false
  next.basic.refresh_window_hours = Number.isFinite(next.basic.refresh_window_hours)
    ? next.basic.refresh_window_hours
    : 1
  next.basic.register_default_count = Number.isFinite(next.basic.register_default_count)
    ? next.basic.register_default_count
    : 1
  next.basic.register_domain = typeof next.basic.register_domain === 'string'
    ? next.basic.register_domain
    : ''
  next.basic.duckmail_api_key = typeof next.basic.duckmail_api_key === 'string'
    ? next.basic.duckmail_api_key
    : ''
  next.basic.gptmail_base_url = typeof next.basic.gptmail_base_url === 'string'
    ? next.basic.gptmail_base_url
    : 'https://mail.chatgpt.org.uk'
  next.basic.gptmail_api_key = typeof next.basic.gptmail_api_key === 'string'
    ? next.basic.gptmail_api_key
    : ''
  next.basic.moemail_base_url = typeof next.basic.moemail_base_url === 'string'
    ? next.basic.moemail_base_url
    : 'https://mail.ishalumi.me'
  next.basic.moemail_api_key = typeof next.basic.moemail_api_key === 'string'
    ? next.basic.moemail_api_key
    : ''
  next.basic.moemail_domain = typeof next.basic.moemail_domain === 'string'
    ? next.basic.moemail_domain
    : ''
  next.basic.register_mail_provider = typeof next.basic.register_mail_provider === 'string'
    ? next.basic.register_mail_provider
    : 'duckmail'
  next.basic.register_mail_prefix = typeof next.basic.register_mail_prefix === 'string'
    ? next.basic.register_mail_prefix
    : ''
  next.automation = next.automation || {}
  next.automation.stealth_enabled = next.automation.stealth_enabled ?? true
  next.automation.webrtc_protect = next.automation.webrtc_protect ?? true
  next.automation.timezone = typeof next.automation.timezone === 'string'
    ? next.automation.timezone
    : ''
  next.automation.geo_latitude = Number.isFinite(next.automation.geo_latitude)
    ? next.automation.geo_latitude
    : null
  next.automation.geo_longitude = Number.isFinite(next.automation.geo_longitude)
    ? next.automation.geo_longitude
    : null
  next.automation.geo_accuracy = Number.isFinite(next.automation.geo_accuracy)
    ? next.automation.geo_accuracy
    : 50
  next.automation.random_delay_min_ms = Number.isFinite(next.automation.random_delay_min_ms)
    ? next.automation.random_delay_min_ms
    : 120
  next.automation.random_delay_max_ms = Number.isFinite(next.automation.random_delay_max_ms)
    ? next.automation.random_delay_max_ms
    : 380
  next.automation.between_account_min_seconds = Number.isFinite(next.automation.between_account_min_seconds)
    ? next.automation.between_account_min_seconds
    : 0
  next.automation.between_account_max_seconds = Number.isFinite(next.automation.between_account_max_seconds)
    ? next.automation.between_account_max_seconds
    : 0
  next.retry = next.retry || {}
  next.retry.stream_auto_retry_times = Number.isFinite(next.retry.stream_auto_retry_times)
    ? next.retry.stream_auto_retry_times
    : 1
  next.retry.auto_refresh_accounts_seconds = Number.isFinite(next.retry.auto_refresh_accounts_seconds)
    ? next.retry.auto_refresh_accounts_seconds
    : 60
  localSettings.value = next
})

onMounted(async () => {
  await settingsStore.loadSettings()
})

const handleSave = async () => {
  if (!localSettings.value) return
  errorMessage.value = ''
  isSaving.value = true

  try {
    await settingsStore.updateSettings(localSettings.value)
    toast.success('设置保存成功')
  } catch (error: any) {
    errorMessage.value = error.message || '保存失败'
    toast.error(error.message || '保存失败')
  } finally {
    isSaving.value = false
  }
}
</script>
