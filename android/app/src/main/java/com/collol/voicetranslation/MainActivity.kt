package com.collol.voicetranslation

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.drawable.Drawable
import android.os.Bundle
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.graphics.drawable.toBitmap

private data class LaunchableApp(
    val label: String,
    val packageName: String,
    val icon: Drawable,
)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { MaterialTheme { SetupScreen { finish() } } }
    }
}

@Composable
private fun SetupScreen(onClose: () -> Unit) {
    val context = LocalContext.current
    val packageManager = context.packageManager
    val preferences = remember(context) {
        context.getSharedPreferences("voice_translation_setup", Context.MODE_PRIVATE)
    }
    var appRefresh by remember { mutableIntStateOf(0) }
    val launchableApps = remember(packageManager, appRefresh) { loadLaunchableApps(packageManager) }
    DisposableEffect(context) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) appRefresh++
        }
        (context as ComponentActivity).lifecycle.addObserver(observer)
        onDispose { (context as ComponentActivity).lifecycle.removeObserver(observer) }
    }
    val languages = listOf("Tiếng Việt", "English", "中文", "日本語", "한국어", "Français")
    var languageA by rememberSaveable { mutableStateOf(preferences.getString("language_a", languages[0]) ?: languages[0]) }
    var languageB by rememberSaveable { mutableStateOf(preferences.getString("language_b", languages[1]) ?: languages[1]) }
    var selectedAppPackage by rememberSaveable { mutableStateOf(preferences.getString("selected_app_package", null)) }
    var checked by rememberSaveable { mutableStateOf(false) }
    val selectedApp = launchableApps.firstOrNull { it.packageName == selectedAppPackage }
    val selectedAppLabel = selectedApp?.label ?: "Chưa chọn ứng dụng"

    Scaffold { padding ->
        Column(
            Modifier.padding(padding).fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(20.dp),
        ) {
            Text("Voice Translation", style = MaterialTheme.typography.headlineMedium)
            Text("Thiết lập cuộc gọi", style = MaterialTheme.typography.titleLarge)
            Text("Bản phát triển • Chưa hỗ trợ dịch cuộc gọi", color = MaterialTheme.colorScheme.error)
            Text("Bạn (A) điều khiển dịch. Người B tham gia cuộc gọi thông thường, không cần cài công cụ dịch.")

            Text("Ứng dụng cuộc gọi", style = MaterialTheme.typography.titleMedium)
            Text("Chọn ứng dụng A sẽ mở để gọi. Bản xem trước chưa theo dõi hoặc chèn audio nền từ ứng dụng khác.", style = MaterialTheme.typography.bodySmall)
            AppPicker(
                value = selectedAppLabel,
                apps = launchableApps,
                onSelect = { selectedAppPackage = it.packageName; preferences.edit().putString("selected_app_package", it.packageName).apply(); checked = false },
            )
            if (selectedApp != null) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Image(
                        bitmap = selectedApp.icon.toBitmap(48, 48).asImageBitmap(),
                        contentDescription = null,
                        modifier = Modifier.size(48.dp),
                    )
                    Column(Modifier.weight(1f)) {
                        Text(selectedApp.label, style = MaterialTheme.typography.bodyLarge)
                        Text(selectedApp.packageName, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    OutlinedButton(onClick = {
                        packageManager.getLaunchIntentForPackage(selectedApp.packageName)?.let(context::startActivity)
                    }) { Text("Mở") }
                }
            }

            LanguagePicker("Ngôn ngữ của bạn (A)", languageA, languages) { languageA = it; preferences.edit().putString("language_a", it).apply(); checked = false }
            LanguagePicker("Ngôn ngữ người nghe (B)", languageB, languages) { languageB = it; preferences.edit().putString("language_b", it).apply(); checked = false }
            OutlinedButton(onClick = {
                val previous = languageA
                languageA = languageB
                languageB = previous
                preferences.edit().putString("language_a", languageA).putString("language_b", languageB).apply()
                checked = false
            }, modifier = Modifier.fillMaxWidth()) { Text("Đổi ngôn ngữ hai bên") }
            if (languageA == languageB) {
                Text("Chọn hai ngôn ngữ khác nhau để dịch.", color = MaterialTheme.colorScheme.error)
            }
            HorizontalDivider()
            Text("Ứng dụng đã chọn: ${selectedApp?.label ?: "chưa chọn"}", style = MaterialTheme.typography.titleSmall)
            Text("Theo dõi cuộc gọi nền: chưa tích hợp", style = MaterialTheme.typography.titleMedium)
            Text("Chọn ứng dụng chỉ lưu mục tiêu cấu hình và mở ứng dụng đó. Android không tự cho phép app này đọc hoặc chèn audio vào mọi ứng dụng gọi điện.")
            Button(
                onClick = { checked = true },
                enabled = selectedApp != null && languageA != languageB,
                modifier = Modifier.fillMaxWidth(),
            ) { Text("Kiểm tra khả năng bắt đầu") }
            if (checked) {
                Text("Chưa thể bắt đầu dịch. Cần tích hợp và kiểm chứng audio VoIP hai chiều cùng bộ xử lý dịch trước. Không có phiên dịch nào được khởi chạy.", color = MaterialTheme.colorScheme.error)
            }
            OutlinedButton(onClick = onClose, modifier = Modifier.fillMaxWidth()) { Text("Đóng") }
            Text("Danh sách ứng dụng lấy từ các app có thể mở trên thiết bị. Cấu hình được lưu trên thiết bị này.", style = MaterialTheme.typography.bodySmall)
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AppPicker(
    value: String,
    apps: List<LaunchableApp>,
    onSelect: (LaunchableApp) -> Unit,
) {
    var expanded by remember { mutableStateOf(false) }
    ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }) {
        OutlinedTextField(
            value = value,
            onValueChange = {},
            readOnly = true,
            label = { Text("Ứng dụng gọi trên A") },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) },
            modifier = Modifier.fillMaxWidth().menuAnchor(),
        )
        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            if (apps.isEmpty()) {
                DropdownMenuItem(text = { Text("Không tìm thấy ứng dụng có thể mở") }, onClick = { expanded = false })
            } else {
                apps.forEach { app ->
                    DropdownMenuItem(
                        text = { Text(app.label) },
                        onClick = { onSelect(app); expanded = false },
                    )
                }
            }
        }
    }
}

private fun loadLaunchableApps(packageManager: PackageManager): List<LaunchableApp> {
    val intent = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
    return packageManager.queryIntentActivities(intent, PackageManager.MATCH_ALL)
        .mapNotNull { resolveInfo ->
            val appInfo = resolveInfo.activityInfo?.applicationInfo ?: return@mapNotNull null
            val packageName = appInfo.packageName
            if (packageName == "com.collol.voicetranslation") return@mapNotNull null
            LaunchableApp(
                label = appInfo.loadLabel(packageManager).toString().ifBlank { packageName },
                packageName = packageName,
                icon = appInfo.loadIcon(packageManager),
            )
        }
        .distinctBy { it.packageName }
        .sortedBy { it.label.lowercase() }
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
