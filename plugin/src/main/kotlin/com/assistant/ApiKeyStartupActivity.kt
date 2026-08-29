package com.assistant

import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.project.Project
import com.intellij.openapi.startup.StartupActivity

/**
 * 首次使用(尚未配置 API key)时,自动弹出「接入你的 API」弹窗。
 * 配置过之后就不再自动弹出,可通过 Tools → 接入你的 API… 重新打开。
 */
class ApiKeyStartupActivity : StartupActivity.DumbAware {
    override fun runActivity(project: Project) {
        // 联动启动:在后台把后端拉起来(若尚未运行)
        Thread { BackendStarter.ensureStarted() }.start()
        // 后台检查插件新版本,有新版本则弹通知
        VersionCheck.check(project)
        // 启动自检:检查后端 + API key,并通知结果
        SelfCheck.run(project)
        // 只有还没配置 key 时才弹配置框;已配置则静默
        if (AssistantSettings.getInstance().state.apiKey.isBlank()) {
            ApplicationManager.getApplication().invokeLater {
                ApiConfigDialog(project).show()
            }
        }
    }
}
