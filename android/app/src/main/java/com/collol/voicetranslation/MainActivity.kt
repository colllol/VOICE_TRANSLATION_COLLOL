package com.collol.voicetranslation

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { MaterialTheme { SetupScreen { finish() } } }
    }
}

@Composable
private fun SetupScreen(onClose: () -> Unit) {
    val languages = listOf("Tiếng Việt", "English", "中文", "日本語", "한국어", "Français")
    var languageA by rememberSaveable { mutableStateOf(languages[0]) }
    var languageB by rememberSaveable { mutableStateOf(languages[1]) }
    var checked by rememberSaveable { mutableStateOf(false) }
    Scaffold { padding ->
        Column(
            Modifier.padding(padding).fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(20.dp),
        ) {
            Text("Voice Translation", style = MaterialTheme.typography.headlineMedium)
            Text("Thiết lập cuộc gọi", style = MaterialTheme.typography.titleLarge)
            Text("Bản phát triển • Chưa hỗ trợ dịch cuộc gọi", color = MaterialTheme.colorScheme.error)
            Text("Bạn (A) điều khiển dịch. Người B tham gia cuộc gọi thông thường, không cần cài công cụ dịch.")
            LanguagePicker("Ngôn ngữ của bạn (A)", languageA, languages) { languageA = it; checked = false }
            LanguagePicker("Ngôn ngữ người nghe (B)", languageB, languages) { languageB = it; checked = false }
            OutlinedButton(onClick = {
                val previous = languageA
                languageA = languageB
                languageB = previous
                checked = false
            }, modifier = Modifier.fillMaxWidth()) { Text("Đổi ngôn ngữ hai bên") }
            if (languageA == languageB) {
                Text("Chọn hai ngôn ngữ khác nhau để dịch.", color = MaterialTheme.colorScheme.error)
            }
            HorizontalDivider()
            Text("Kết nối cuộc gọi: chưa tích hợp", style = MaterialTheme.typography.titleMedium)
            Text("Chưa có kết nối VoIP và bộ xử lý dịch. Ứng dụng không thu mic, không gửi audio và không tự dịch cuộc gọi ở ứng dụng khác.")
            Button(onClick = { checked = true }, enabled = languageA != languageB, modifier = Modifier.fillMaxWidth()) {
                Text("Kiểm tra khả năng bắt đầu")
            }
            if (checked) {
                Text("Chưa thể bắt đầu dịch. Cần tích hợp và kiểm chứng audio VoIP hai chiều cùng bộ xử lý dịch trước. Không có phiên dịch nào được khởi chạy.", color = MaterialTheme.colorScheme.error)
            }
            OutlinedButton(onClick = onClose, modifier = Modifier.fillMaxWidth()) { Text("Đóng") }
            Text("Danh sách ngôn ngữ là cấu hình dự kiến, chưa xác nhận chất lượng dịch. Lựa chọn được giữ khi xoay màn hình; chưa lưu cấu hình lâu dài.", style = MaterialTheme.typography.bodySmall)
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun LanguagePicker(label: String, value: String, languages: List<String>, onSelect: (String) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }) {
        OutlinedTextField(
            value = value, onValueChange = {}, readOnly = true,
            label = { Text(label) },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) },
            modifier = Modifier.fillMaxWidth().menuAnchor(),
        )
        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            languages.forEach { language ->
                DropdownMenuItem(text = { Text(language) }, onClick = { onSelect(language); expanded = false })
            }
        }
    }
}
