package com.assistant

import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent

/** 菜单/右键入口:把选中的代码保存到文件库(片段)。 */
class SaveSnippetAction : AnAction() {
    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project ?: return
        SnippetSaver.saveCurrent(project)
    }
}
