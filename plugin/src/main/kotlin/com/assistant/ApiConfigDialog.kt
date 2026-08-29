package com.assistant

import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.DialogWrapper
import com.intellij.ui.components.JBCheckBox
import com.intellij.ui.components.JBLabel
import com.intellij.ui.components.JBPasswordField
import com.intellij.ui.components.JBTextField
import java.awt.BorderLayout
import java.awt.FlowLayout
import java.awt.GridBagConstraints
import java.awt.GridBagLayout
import java.awt.Insets
import java.awt.Toolkit
import java.awt.datatransfer.DataFlavor
import javax.swing.JButton
import javax.swing.JComponent
import javax.swing.JPanel

/**
 * 「接入你的 API」配置弹窗:
 * 填自己的 DeepSeek API key(只存本机)、云端「用户名 + 令牌」,
 * 以及后端联动启动设置(可选)。
 * API key 支持自动识别剪贴板,或点「粘贴」按钮;
 * 密码框带「眼睛」显示/隐藏与「X」一键清空。
 */
class ApiConfigDialog(private val project: Project?) : DialogWrapper(project, true) {

    private val apiKeyField = JBPasswordField().apply { columns = 30 }
    private val usernameField = JBTextField().apply { columns = 30 }
    private val tokenField = JBPasswordField().apply { columns = 30 }
    private val autoStartBox = JBCheckBox("打开 PyCharm 时自动启动后端")
    private val backendDirField = JBTextField().apply { columns = 30 }
    private val pythonPathField = JBTextField().apply { columns = 30 }

    init {
        title = "接入你的 API"
        val s = AssistantSettings.getInstance().state
        apiKeyField.text = s.apiKey
        usernameField.text = s.username
        tokenField.text = s.token
        autoStartBox.isSelected = s.autoStartBackend
        backendDirField.text = s.backendDir
        pythonPathField.text = s.pythonPath
        // 若尚未填过 key,且剪贴板里已有形如 sk-xxx 的 key,自动填上
        if (String(apiKeyField.password).isBlank()) {
            readClipboardText().trim().let { if (looksLikeApiKey(it)) apiKeyField.text = it }
        }
        init()
    }

    override fun createCenterPanel(): JComponent {
        val panel = JPanel(GridBagLayout())
        val c = GridBagConstraints().apply {
            insets = Insets(4, 4, 4, 4)
            anchor = GridBagConstraints.WEST
            fill = GridBagConstraints.HORIZONTAL
        }

        fun title(y: Int, text: String) {
            c.gridx = 0; c.gridy = y; c.gridwidth = 2; c.weightx = 1.0
            panel.add(JBLabel(text), c)
            c.gridwidth = 1; c.weightx = 0.0
        }
        fun row(y: Int, label: String, comp: JComponent, hint: String) {
            c.gridx = 0; c.gridy = y; c.weightx = 0.0
            panel.add(JBLabel(label), c)
            c.gridx = 1; c.weightx = 1.0
            panel.add(comp, c)
            c.gridx = 0; c.gridy = y + 1; c.gridwidth = 2; c.weightx = 0.0
            panel.add(JBLabel("<html><font color='gray' size='-1'>$hint</font></html>"), c)
            c.gridwidth = 1
        }

        title(0, "<html><b>请接入你需要调用的 api</b></html>")

        var y = 1
        row(y, "DeepSeek API Key:", passwordFieldWithButtons(apiKeyField, true), "复制过 key 会自动识别;没识别到就点「粘贴」"); y += 2
        row(y, "用户名:", usernameField, "云端文件库的多用户标识,可自定义"); y += 2
        row(y, "令牌:", passwordFieldWithButtons(tokenField, false), "你的私密令牌,配合用户名区分各自的库"); y += 2

        c.gridx = 0; c.gridy = y; c.gridwidth = 2; c.weightx = 1.0
        panel.add(JBLabel("<html><br><b>后端联动启动</b></html>"), c); y += 1
        c.gridx = 0; c.gridy = y; c.gridwidth = 2; c.weightx = 0.0
        panel.add(autoStartBox, c); y += 1
        row(y, "后端目录:", backendDirField, "含 backend 文件夹的那层,如 D:\\ai-code-assistant"); y += 2
        row(y, "Python 路径:", pythonPathField, "留空则自动探测(如 D:\\AI\\python.exe)")

        return panel
    }

    override fun doOKAction() {
        val s = AssistantSettings.getInstance().state
        s.apiKey = String(apiKeyField.password).trim()
        s.username = usernameField.text.trim()
        s.token = String(tokenField.password).trim()
        s.autoStartBackend = autoStartBox.isSelected
        s.backendDir = backendDirField.text.trim()
        s.pythonPath = pythonPathField.text.trim()
        super.doOKAction()
    }

    /** 给密码框加上「眼睛」显示/隐藏、「X」清空;withPaste 时再附一个「粘贴」按钮。 */
    private fun passwordFieldWithButtons(field: JBPasswordField, withPaste: Boolean): JComponent {
        val originalEcho = field.echoChar

        val showBtn = JButton("显示").apply {
            isContentAreaFilled = false
            isBorderPainted = false
            isFocusable = false
            toolTipText = "显示/隐藏内容"
            addActionListener {
                val visible = field.echoChar == 0.toChar()
                field.echoChar = if (visible) originalEcho else 0.toChar()
                text = if (visible) "显示" else "隐藏"
            }
        }
        val clearBtn = JButton("×").apply {
            isContentAreaFilled = false
            isBorderPainted = false
            isFocusable = false
            toolTipText = "清空"
            addActionListener { field.text = "" }
        }

        val buttons = JPanel(FlowLayout(FlowLayout.LEFT, 0, 0))
        if (withPaste) {
            buttons.add(JButton("粘贴").apply {
                isFocusable = false
                addActionListener {
                    val clip = readClipboardText().trim()
                    if (clip.isNotBlank()) field.text = clip
                }
            })
        }
        buttons.add(showBtn)
        buttons.add(clearBtn)

        return JPanel(BorderLayout(0, 0)).apply {
            add(field, BorderLayout.CENTER)
            add(buttons, BorderLayout.EAST)
        }
    }

    private fun readClipboardText(): String {
        return try {
            val clipboard = Toolkit.getDefaultToolkit().systemClipboard
            if (clipboard.isDataFlavorAvailable(DataFlavor.stringFlavor)) {
                clipboard.getData(DataFlavor.stringFlavor) as? String ?: ""
            } else {
                ""
            }
        } catch (_: Exception) {
            ""
        }
    }

    private fun looksLikeApiKey(s: String): Boolean {
        return s.startsWith("sk-") && s.length >= 16
    }
}
