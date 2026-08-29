package com.assistant

import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent

class ConfigureAction : AnAction("接入你的 API…", "配置 DeepSeek API key 与云端身份", null) {
    override fun actionPerformed(e: AnActionEvent) {
        ApiConfigDialog(e.project).show()
    }
}
