# 🖥️ JustRunMy.App 自动续期 (多账号无序签到可proxy版)

> **本项目支持多账号无限扩展，随机执行顺序，精准秒级延迟，带多协议代理支持。**

## 🌟 核心特色

- 🎲 **无序执行**：不再按 EML_1, EML_2 的顺序排队，每次运行都会随机打乱账号执行顺序，彻底模拟多人随机操作。
- 📅 **智能排班**：确保每 1~2 天签到一次。
- ⏰ **精准延迟**：北京时间 06:00 准时触发后，进入 0~4 小时随机等待。
- 🌐 **全协议代理**：内置 sing-box 核心，支持 vless/vmess/tuic/hy2/socks5/http等**明文**或**base64编码**协议，实现**固定ip**续签。

---

## ⚡ 快速开始

1. **[Fork]** 本项目到个人仓库。
2. **[Secrets]** 配置账号信息：前往 `Settings` -> `Secrets and variables` -> `Actions`。
3. **[Actions]** 启用工作流：在 `Actions` 页面点击 "Run workflow" 或等待定时触发。
4. **安全时效**：总运行时间严格限制在 6 小时内，防止被 GitHub Actions 强制中断。
---

## 🛠️ 环境变量配置 (Secrets)

| 变量名 (Name) | 是否必填 | 示例值 (Value) | 说明 |
| :--- | :--- | :--- | :--- |
| **EML_1, EML_2...** | 是 | user@example.com | 账号邮箱 (支持无限扩展) |
| **PWD_1, PWD_2...** | 是 | your_password | 账号密码 (对应 EML_x) |
| **PROXY_URL** | 否 | vless://uuid@host:port... | 代理链接 (支持全协议) |
| **TG_TOKEN** | 否 | 123456:ABC... | Telegram 机器人 Token |
| **TG_ID** | 否 | 987654321 | Telegram 用户 ID |

### 总结如下图
<img width="1428" height="817" alt="26-03-10-19-44-30" src="https://github.com/user-attachments/assets/a6351243-793f-49bc-9841-c0e619ffe9e7" />

---

## ⚠️ 调试与报错

若 Actions 运行失败：
1. 在任务页面的 **[Artifacts]** 区域下载 `debug-acc-X`。
2. 查看压缩包内的 `.png` 截图，确认是网络超时还是验证码识别失败。
3. **常见问题**：
   - `未找到 ACC 或 ACC_PWD`：请检查 Secrets 命名是否为 `EML_1` / `PWD_1` 格式。
   - `Turnstile 验证失败`：通常是代理质量不佳或 Cloudflare 策略更新，建议更换 PROXY_URL。

---

## 🌟 特别鸣谢

本项目核心续期逻辑参考并使用了以下开源项目：
👉 原作者项目: [mangguo88/JustRunMy-Renew](https://github.com/mangguo88/JustRunMy-Renew)
在此感谢 mangguo88 提供的物理模拟算法支持。
 提供的稳定物理模拟续期算法和proxy代理想法。
