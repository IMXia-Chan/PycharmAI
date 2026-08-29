package com.assistant

import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.DialogWrapper
import com.intellij.ui.components.JBScrollPane
import java.awt.Dimension
import java.awt.event.ActionEvent
import javax.swing.Action
import javax.swing.JComponent
import javax.swing.JTextArea

/** 展示 AI 返回的文本/代码;若传入 onReplace,则多一个「替换选区」按钮。 */
class AiResultDialog(
    project: Project,
    title: String,
    private val content: String,
    private val onReplace: (() -> Unit)? = null,
) : DialogWrapper(project) {

    private val area = JTextArea(content).apply {
        lineWrap = true
        wrapStyleWord = true
        isEditable = false
    }

    init {
        this.title = title
        init()
    }

    override fun createCenterPanel(): JComponent {
        area.preferredSize = Dimension(680, 420)
        return JBScrollPane(area)
    }

    override fun createActions(): Array<Action> {
        val actions = mutableListOf<Action>()
        if (onReplace != null) {
            actions.add(object : DialogWrapperAction("替换选区") {
                override fun doAction(e: ActionEvent) {
                    onReplace.invoke()
                    close(OK_EXIT_CODE)
                }
            })
        }
        actions.add(okAction)
        return actions.toTypedArray()
    }
}
