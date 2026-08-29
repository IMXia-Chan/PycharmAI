package com.assistant

import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.progress.ProgressIndicator
import com.intellij.openapi.progress.ProgressManager
import com.intellij.openapi.progress.Task
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.SimpleToolWindowPanel
import com.intellij.openapi.wm.ToolWindow
import com.intellij.openapi.wm.ToolWindowFactory
import com.intellij.ui.components.JBScrollPane
import java.awt.BorderLayout
import java.awt.event.ActionEvent
import javax.swing.AbstractAction
import javax.swing.JButton
import javax.swing.JComponent
import javax.swing.JEditorPane
import javax.swing.JPanel
import javax.swing.JTextArea
import javax.swing.KeyStroke
import javax.swing.SwingUtilities

/** 「AI 问答」工具窗口:底部输入问题,顶部显示对话历史。 */
class ChatToolWindowFactory : ToolWindowFactory {
    override fun createToolWindowContent(project: Project, toolWindow: ToolWindow) {
        val content = toolWindow.contentManager.factory.createContent(ChatPanel(project), "", false)
        toolWindow.contentManager.addContent(content)
    }
}

private class ChatPanel(private val myProject: Project) : SimpleToolWindowPanel(true, true) {

    private val history = StringBuilder()
    private val historyPane = JEditorPane().apply {
        contentType = "text/html"
        isEditable = false
        text = render()
    }
    private val inputArea = JTextArea(4, 30).apply {
        lineWrap = true
        wrapStyleWord = true
    }
    private val sendBtn = JButton("发送")
    private val clearBtn = JButton("清空对话")

    init {
        val center = JPanel(BorderLayout(0, 6))
        center.add(JBScrollPane(historyPane), BorderLayout.CENTER)
        center.add(inputPanel(), BorderLayout.SOUTH)
        setContent(center)

        sendBtn.addActionListener { send() }
        clearBtn.addActionListener {
            history.setLength(0)
            historyPane.text = render()
        }

        // Ctrl+Enter 也能发送
        val sendAction = object : AbstractAction() {
            override fun actionPerformed(e: ActionEvent) = send()
        }
        inputArea.inputMap.put(KeyStroke.getKeyStroke("control ENTER"), "send")
        inputArea.actionMap.put("send", sendAction)
    }

    /** 面板挂载到窗口后,把焦点放到输入框,否则刚打开时打字会落到别处。 */
    override fun addNotify() {
        super.addNotify()
        SwingUtilities.invokeLater { inputArea.requestFocusInWindow() }
    }

    private fun inputPanel(): JComponent {
        val p = JPanel(BorderLayout(0, 4))
        p.add(JBScrollPane(inputArea), BorderLayout.CENTER)
        val btns = JPanel(BorderLayout(0, 0))
        btns.add(sendBtn, BorderLayout.EAST)
        btns.add(clearBtn, BorderLayout.WEST)
        p.add(btns, BorderLayout.SOUTH)
        return p
    }

    private fun send() {
        val question = inputArea.text.trim()
        if (question.isBlank()) return
        append("我", question)
        inputArea.text = ""
        ProgressManager.getInstance().run(object : Task.Backgroundable(myProject, "AI 正在回答…", false) {
            override fun run(indicator: ProgressIndicator) {
                val reply = try {
                    BackendClient.chat(question)
                } catch (ex: Exception) {
                    "请求失败:${ex.message ?: "请确认后端已启动"}"
                }
                ApplicationManager.getApplication().invokeLater { append("AI", reply) }
            }
        })
    }

    private fun append(who: String, text: String) {
        history.append("<p><b>").append(escape(who)).append("</b><br>")
        history.append(escape(text).replace("\n", "<br>")).append("</p><hr>")
        historyPane.text = render()
        historyPane.caretPosition = historyPane.document.length
    }

    private fun render(): String =
        "<html><body style='font-family:sans-serif;font-size:13px'>" + history + "</body></html>"

    private fun escape(s: String): String =
        s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
}
