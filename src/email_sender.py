"""
邮箱发送模块 — 通过 163 SMTP 发送 HTML 邮件
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr, formatdate, make_msgid
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

CST = timezone(timedelta(hours=8))


class EmailSender:
    """SMTP 邮件发送器"""

    def __init__(self, smtp_server: str, smtp_port: int, from_addr: str,
                 password: str, use_ssl: bool = True):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.from_addr = from_addr
        self.password = password
        self.use_ssl = use_ssl

    def send(self, to_addr: str, subject: str, html_body: str,
             plain_body: str = "") -> bool:
        """
        发送 HTML 邮件

        Args:
            to_addr:   收件人邮箱
            subject:   邮件主题
            html_body: HTML 格式的邮件正文
            plain_body: 纯文本备选（当客户端不支持 HTML 时显示）

        Returns:
            是否发送成功
        """
        try:
            # 构建 MIME 邮件
            msg = MIMEMultipart("alternative")
            msg["From"] = formataddr(("每日早报", self.from_addr))
            msg["To"] = to_addr
            msg["Subject"] = Header(subject, "utf-8")
            msg["Date"] = formatdate(localtime=True)
            msg["Message-ID"] = make_msgid(domain=self.from_addr.split("@")[-1])

            # 纯文本备选
            if not plain_body:
                plain_body = self._html_to_plain(html_body)

            msg.attach(MIMEText(plain_body, "plain", "utf-8"))
            msg.attach(MIMEText(html_body, "html", "utf-8"))

            # 连接 SMTP 并发送
            logger.info(f"正在连接 {self.smtp_server}:{self.smtp_port} ...")

            if self.use_ssl:
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=30)
            else:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30)
                server.starttls()

            server.login(self.from_addr, self.password)
            server.send_message(msg)
            server.quit()

            logger.info(f"邮件发送成功 → {to_addr}")
            return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"邮箱认证失败: {e}")
            logger.error("请检查: 1) 邮箱地址是否正确  2) 是否使用的是 SMTP 授权码（非登录密码）")
            return False
        except smtplib.SMTPConnectError as e:
            logger.error(f"SMTP 连接失败: {e}")
            return False
        except Exception as e:
            logger.error(f"邮件发送异常: {type(e).__name__}: {e}")
            return False

    @staticmethod
    def _html_to_plain(html: str) -> str:
        """简单的 HTML → 纯文本转换"""
        import re
        text = html
        # 替换常见标签
        text = re.sub(r"<br\s*/?>", "\n", text)
        text = re.sub(r"</p>", "\n\n", text)
        text = re.sub(r"</li>", "\n", text)
        text = re.sub(r"</h[1-6]>", "\n\n", text)
        text = re.sub(r"</(ol|ul|div|tr|hr)>", "\n", text)
        text = re.sub(r"<[^>]+>", "", text)
        # 合并多余空行
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
