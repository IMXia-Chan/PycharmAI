package com.assistant

import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.components.PersistentStateComponent
import com.intellij.openapi.components.State
import com.intellij.openapi.components.Storage

@State(name = "PythonAssistantSettings", storages = [Storage("python-assistant.xml")])
class AssistantSettings : PersistentStateComponent<AssistantSettings.State> {

    data class State(
        var backendUrl: String = "http://127.0.0.1:8000",
        var searchUrl: String = "https://www.bing.com/search?q=",
        // 每个用户自己的 DeepSeek API key(只保存在本机)
        var apiKey: String = "",
        // 云端文件库的多用户身份(用户名 + 令牌)
        var username: String = "",
        var token: String = "",
        // 后端联动启动:打开 PyCharm 时自动拉起后端
        var autoStartBackend: Boolean = true,
        var pythonPath: String = "",                      // 留空则自动探测 python
        var backendDir: String = "D:\\ai-code-assistant", // 后端项目根目录(含 backend 文件夹的那层)
    )

    private var myState = State()

    override fun getState(): State = myState

    override fun loadState(state: State) {
        myState = state
    }

    companion object {
        fun getInstance(): AssistantSettings =
            ApplicationManager.getApplication().getService(AssistantSettings::class.java)
    }
}
