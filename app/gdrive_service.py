import re
import html
import urllib.parse
from html.parser import HTMLParser
from typing import Dict, List, Optional, Tuple, Any, Set
import requests

from app.direct_downloader import format_bytes_str

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
}


class _EmbeddedFolderParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_title = False
        self.title_parts = []
        self.title = ""
        
        self.in_a = False
        self.current_href = ""
        self.current_text = []
        self.links: List[Tuple[str, str]] = []

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self.in_title = True
        elif tag == "a":
            attrs_dict = dict(attrs)
            href = attrs_dict.get("href", "")
            if href:
                self.in_a = True
                self.current_href = href
                self.current_text = []

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
            self.title = html.unescape("".join(self.title_parts)).strip()
        elif tag == "a" and self.in_a:
            text = html.unescape("".join(self.current_text)).strip()
            self.links.append((self.current_href, text))
            self.in_a = False
            self.current_href = ""
            self.current_text = []

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)
        elif self.in_a:
            self.current_text.append(data)


class GDriveService:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self._url_cache: Dict[str, Tuple[str, Optional[str], Optional[str], bool]] = {}

    def set_cookie(self, cookie_str: Optional[str] = None):
        """Cấu hình Cookie tài khoản Google để tải với hạn mức cao và bypass giới hạn nặc danh."""
        if cookie_str and cookie_str.strip():
            self.session.headers["Cookie"] = cookie_str.strip()
        else:
            self.session.headers.pop("Cookie", None)

    @staticmethod
    def parse_gdrive_url(url: str) -> Tuple[Optional[str], str]:
        """
        Phân tích URL Google Drive và trả về (resource_id, resource_type).
        resource_type có thể là: 'folder', 'file', 'docs', 'sheets', 'slides' hoặc 'unknown'.
        """
        url_clean = url.strip()
        if not url_clean:
            return None, "unknown"

        # Đơn giản hóa nếu người dùng chỉ nhập ID
        if re.match(r"^([-\w]{25,})$", url_clean):
            # Mặc định thử folder hoặc file
            return url_clean, "folder"

        parsed = urllib.parse.urlparse(url_clean)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # 1. Thư mục (Folder)
        folder_match = re.search(r"/drive/(?:u/[0-9]+/)?folders/([-\w]{25,})", path)
        if folder_match:
            return folder_match.group(1), "folder"

        if "folderview" in path and "id" in query:
            return query["id"][0], "folder"

        if "embeddedfolderview" in path and "id" in query:
            return query["id"][0], "folder"

        # 2. Google Docs / Sheets / Slides
        docs_match = re.search(r"/(document|spreadsheets|presentation)/d/([-\w]{25,})", path)
        if docs_match:
            kind, doc_id = docs_match.groups()
            return doc_id, kind

        # 3. File thông thường
        file_match = re.search(r"/file/(?:u/[0-9]+/)?d/([-\w]{25,})", path)
        if file_match:
            return file_match.group(1), "file"

        # 4. Tham số truy vấn chung ?id=
        if "id" in query:
            res_id = query["id"][0]
            # Nếu path có chứa uc, download hoặc open
            if "uc" in path or "download" in path:
                return res_id, "file"
            if "open" in path:
                # 'open?id=' thường được chia sẻ cho file, mặc định là file
                return res_id, "file"
            return res_id, "file"

        return None, "unknown"

    @staticmethod
    def make_direct_download_url(file_id: str, kind: str = "file") -> str:
        """
        Tạo URL tải trực tiếp tối ưu cho IDM.
        Thêm &confirm=t để bỏ qua cảnh báo dung lượng lớn của Google.
        """
        if kind == "document":
            return f"https://docs.google.com/document/d/{file_id}/export?format=pdf"
        elif kind == "spreadsheets":
            return f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx"
        elif kind == "presentation":
            return f"https://docs.google.com/presentation/d/{file_id}/export?format=pptx"
        else:
            return f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"

    @staticmethod
    def make_uc_url(file_id: str) -> str:
        return f"https://drive.google.com/uc?export=download&id={file_id}"

    def resolve_direct_download_url(self, file_id: str, kind: str = "file", cookie: Optional[str] = None) -> Tuple[str, Optional[str], Optional[str], bool]:
        """
        Tự động bypass trang cảnh báo virus quét tệp dung lượng lớn (>100MB) của Google Drive.
        Trích xuất UUID token và thông tin tên/kích thước file từ Google Drive.
        Trả về (direct_download_url_with_uuid, resolved_file_name, resolved_file_size_str, is_quota_exceeded).
        """
        if kind in ("document", "spreadsheets", "presentation"):
            return self.make_direct_download_url(file_id, kind), None, None, False

        cache_key = f"{file_id}_{kind}"
        if not cookie and cache_key in self._url_cache:
            return self._url_cache[cache_key]

        probe_url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download"
        file_name = None
        file_size_str = None
        uuid = None
        is_quota_exceeded = False

        headers = dict(DEFAULT_HEADERS)
        if cookie and cookie.strip():
            headers["Cookie"] = cookie.strip()
        elif "Cookie" in self.session.headers:
            headers["Cookie"] = self.session.headers["Cookie"]

        try:
            r = self.session.get(probe_url, headers=headers, timeout=12, stream=True)
            ct = r.headers.get("content-type", "")

            # Nếu Google trả về trực tiếp file (file nhỏ hoặc không qua trang cảnh báo)
            if "text/html" not in ct:
                cl = r.headers.get("content-length")
                if cl and cl.isdigit():
                    file_size_str = format_bytes_str(int(cl))
                cd = r.headers.get("content-disposition", "")
                fn_m = re.search(r'filename\*?=(?:UTF-8\'\')?["\']?([^"\';]+)["\']?', cd)
                if fn_m:
                    file_name = urllib.parse.unquote(fn_m.group(1).strip())
                res = (f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t", file_name, file_size_str, False)
                self._url_cache[cache_key] = res
                return res

            # Nếu trả về HTML: Kiểm tra Quota Exceeded hay Cảnh báo virus thông thường
            html_text = r.text
            if "Quota exceeded" in html_text or "Too many users have viewed or downloaded" in html_text or "Google Drive - Quota exceeded" in html_text:
                is_quota_exceeded = True

            form_inputs = dict(re.findall(r'<input\s+[^>]*name=["\']([^"\']+)["\'][^>]*value=["\']([^"\']*)["\']', html_text))
            if not form_inputs:
                rev_inputs = re.findall(r'<input\s+[^>]*value=["\']([^"\']*)["\'][^>]*name=["\']([^"\']+)["\']', html_text)
                form_inputs = {k: v for v, k in rev_inputs}

            uuid = form_inputs.get("uuid", "").strip() or None
            at_val = form_inputs.get("at", "").strip() or None

            # Lấy tên file và kích thước hiển thị trong trang cảnh báo
            name_m = re.search(r'<a[^>]+href=["\'][^"\']*open\?id=[^"\']*["\'][^>]*>([^<]+)</a>(?:\s*\(([^)]+)\))?', html_text)
            if name_m:
                file_name = html.unescape(name_m.group(1)).strip()
                if name_m.group(2):
                    file_size_str = name_m.group(2).strip()
            else:
                sub_m = re.search(r'<p class=["\']uc-warning-caption["\'][^>]*>.*?</p>', html_text, re.DOTALL)
                if sub_m:
                    fn_cand = re.search(r'<a[^>]*>([^<]+)</a>', sub_m.group(0))
                    if fn_cand:
                        file_name = html.unescape(fn_cand.group(1)).strip()
        except Exception:
            pass

        url_params = [f"id={file_id}", "export=download", "confirm=t"]
        if uuid:
            url_params.append(f"uuid={uuid}")
        if at_val:
            url_params.append(f"at={at_val}")

        final_url = f"https://drive.usercontent.google.com/download?{'&'.join(url_params)}"
        res = (final_url, file_name, file_size_str, is_quota_exceeded)
        if not is_quota_exceeded:
            self._url_cache[cache_key] = res
        return res

    def get_single_file_info(self, file_id: str, kind: str = "file", cookie: Optional[str] = None) -> Dict[str, Any]:
        """
        Lấy thông tin và link tải trực tiếp cho một tệp tin đơn lẻ, tự động giải quyết UUID để bypass virus warning.
        """
        direct_url, resolved_name, resolved_size, is_quota = self.resolve_direct_download_url(file_id, kind, cookie=cookie)
        uc_url = self.make_uc_url(file_id)
        view_url = f"https://drive.google.com/file/d/{file_id}/view"

        file_name = resolved_name or f"gdrive_file_{file_id}"
        size_bytes = 0
        size_formatted = resolved_size or ("⚠️ Đạt giới hạn 24h" if is_quota else "Không xác định")

        # Nếu chưa có tên file, thử lấy từ trang view
        if not resolved_name or file_name.startswith("gdrive_file_"):
            try:
                headers = dict(DEFAULT_HEADERS)
                if cookie and cookie.strip():
                    headers["Cookie"] = cookie.strip()
                elif "Cookie" in self.session.headers:
                    headers["Cookie"] = self.session.headers["Cookie"]
                r = self.session.get(view_url, headers=headers, timeout=10)
                if r.status_code == 200:
                    og_title_m = re.search(r'<meta property="og:title" content="([^"]+)"', r.text)
                    if og_title_m:
                        file_name = html.unescape(og_title_m.group(1)).strip()
                    else:
                        title_m = re.search(r'<title>(.*?)(?: - Google Drive)?</title>', r.text)
                        if title_m:
                            file_name = html.unescape(title_m.group(1)).strip()
            except Exception:
                pass

        ext = file_name.split(".")[-1].lower() if "." in file_name else ""
        return {
            "id": file_id,
            "name": file_name,
            "path": file_name,
            "folder": "/",
            "kind": kind,
            "extension": ext,
            "size_bytes": size_bytes,
            "size_formatted": size_formatted,
            "download_url": direct_url,
            "smart_url": f"/api/gdrive/download/{file_id}",
            "uc_url": uc_url,
            "view_url": view_url,
            "quota_exceeded": is_quota
        }

    def _parse_folder_page(self, folder_id: str) -> Tuple[str, List[Dict[str, Any]], List[Tuple[str, str]]]:
        """
        Đọc và phân tích trang embeddedfolderview của Google Drive.
        Trả về (folder_title, files_list, subfolders_list).
        """
        url = f"https://drive.google.com/embeddedfolderview?id={folder_id}"
        resp = self.session.get(url, timeout=15)
        if resp.status_code != 200:
            raise ValueError(f"Không thể đọc nội dung thư mục (Mã lỗi {resp.status_code}). Vui lòng đảm bảo thư mục được chia sẻ ở chế độ 'Bất kỳ ai có liên kết' (Anyone with the link).")

        parser = _EmbeddedFolderParser()
        parser.feed(resp.text)

        folder_name = parser.title or f"Folder_{folder_id}"

        files: List[Dict[str, Any]] = []
        subfolders: List[Tuple[str, str]] = []
        seen_ids: Set[str] = set()

        for href, text in parser.links:
            # 1. Kiểm tra File Google Drive chuẩn
            file_match = re.search(r"https://drive\.google\.com/file/d/([-\w]{25,})", href)
            if file_match:
                f_id = file_match.group(1)
                if f_id not in seen_ids:
                    seen_ids.add(f_id)
                    fname = text or f"file_{f_id}"
                    ext = fname.split(".")[-1].lower() if "." in fname else ""
                    files.append({
                        "id": f_id,
                        "name": fname,
                        "kind": "file",
                        "extension": ext,
                        "download_url": self.make_direct_download_url(f_id, "file"),
                        "uc_url": self.make_uc_url(f_id),
                        "view_url": f"https://drive.google.com/file/d/{f_id}/view"
                    })
                continue

            # 2. Kiểm tra Google Docs / Sheets / Slides
            docs_match = re.search(r"https://docs\.google\.com/(\w+)/d/([-\w]{25,})", href)
            if docs_match:
                doc_kind, f_id = docs_match.groups()
                if f_id not in seen_ids:
                    seen_ids.add(f_id)
                    fname = text or f"{doc_kind}_{f_id}"
                    ext = "pdf" if doc_kind == "document" else ("xlsx" if doc_kind == "spreadsheets" else "pptx")
                    if not fname.endswith(f".{ext}"):
                        fname += f".{ext}"
                    files.append({
                        "id": f_id,
                        "name": fname,
                        "kind": doc_kind,
                        "extension": ext,
                        "download_url": self.make_direct_download_url(f_id, doc_kind),
                        "uc_url": self.make_uc_url(f_id),
                        "view_url": href
                    })
                continue

            # 3. Kiểm tra Subfolder
            folder_id_match = re.search(r"/drive/folders/([-\w]{25,})", href) or re.search(r"[?&]id=([-\w]{25,})", href)
            if folder_id_match:
                sub_id = folder_id_match.group(1)
                if sub_id != folder_id and sub_id not in seen_ids:
                    seen_ids.add(sub_id)
                    sub_name = text or f"Subfolder_{sub_id}"
                    subfolders.append((sub_id, sub_name))

        return folder_name, files, subfolders

    def _scan_folder_via_api(self, folder_id: str, api_key: str, max_depth: int = 10) -> Dict[str, Any]:
        """
        Quét thư mục Google Drive sử dụng Google Drive API v3 chính thức (nếu có API Key).
        """
        base_url = "https://www.googleapis.com/drive/v3/files"
        all_files: List[Dict[str, Any]] = []

        try:
            r = requests.get(
                f"{base_url}/{folder_id}",
                params={"fields": "id, name, mimeType", "key": api_key},
                timeout=12
            )
            root_info = r.json()
            root_name = root_info.get("name", f"Folder_{folder_id}")
        except Exception:
            root_name = f"Folder_{folder_id}"

        folder_queue: List[Tuple[str, str, int]] = [(folder_id, root_name, 0)]
        visited: Set[str] = {folder_id}
        folder_count = 0

        while folder_queue:
            curr_id, curr_path, depth = folder_queue.pop(0)
            if depth > max_depth:
                continue

            page_token = None
            while True:
                params = {
                    "q": f"'{curr_id}' in parents and trashed = false",
                    "fields": "nextPageToken, files(id, name, mimeType, size, webViewLink, webContentLink)",
                    "pageSize": 100,
                    "key": api_key
                }
                if page_token:
                    params["pageToken"] = page_token

                resp = requests.get(base_url, params=params, timeout=15)
                if resp.status_code != 200:
                    break

                data = resp.json()
                for item in data.get("files", []):
                    f_id = item["id"]
                    f_name = item["name"]
                    mime = item.get("mimeType", "")

                    if mime == "application/vnd.google-apps.folder":
                        if f_id not in visited and depth < max_depth:
                            visited.add(f_id)
                            folder_count += 1
                            folder_queue.append((f_id, f"{curr_path} / {f_name}", depth + 1))
                    else:
                        size_bytes = int(item.get("size", 0))
                        size_fmt = format_bytes_str(size_bytes) if size_bytes else "Không xác định"

                        kind = "file"
                        if "document" in mime:
                            kind = "document"
                        elif "spreadsheet" in mime:
                            kind = "spreadsheets"
                        elif "presentation" in mime:
                            kind = "presentation"

                        ext = f_name.split(".")[-1].lower() if "." in f_name else ""
                        all_files.append({
                            "id": f_id,
                            "name": f_name,
                            "path": f"{curr_path} / {f_name}",
                            "folder": curr_path,
                            "kind": kind,
                            "extension": ext,
                            "size_bytes": size_bytes,
                            "size_formatted": size_fmt,
                            "download_url": self.make_direct_download_url(f_id, kind),
                            "uc_url": self.make_uc_url(f_id),
                            "view_url": f"https://drive.google.com/file/d/{f_id}/view",
                            "quota_exceeded": False
                        })

                page_token = data.get("nextPageToken")
                if not page_token:
                    break

        return {
            "root_name": root_name,
            "root_id": folder_id,
            "total_files": len(all_files),
            "total_folders": folder_count,
            "files": all_files
        }

    def scan_folder(self, folder_id: str, api_key: Optional[str] = None, max_depth: int = 10, cookie: Optional[str] = None) -> Dict[str, Any]:
        """
        Quét đệ quy toàn bộ thư mục và các thư mục con lồng nhau (nested subfolders).
        Nếu có api_key thì dùng Drive API v3, ngược lại dùng embedded web view (hoàn toàn miễn phí, không cần key).
        """
        if api_key and api_key.strip():
            return self._scan_folder_via_api(folder_id, api_key.strip(), max_depth=max_depth)

        all_files: List[Dict[str, Any]] = []
        visited_folders: Set[str] = set()
        folder_count = 0

        # Lấy thông tin thư mục gốc
        try:
            root_name, initial_files, initial_subfolders = self._parse_folder_page(folder_id)
        except Exception as e:
            raise ValueError(f"Không thể kết nối đến thư mục Google Drive: {str(e)}")

        visited_folders.add(folder_id)

        # Thêm file ở thư mục gốc
        for f in initial_files:
            f["path"] = f"{root_name} / {f['name']}"
            f["folder"] = root_name
            f["size_bytes"] = 0
            f["size_formatted"] = "Không xác định"
            f["quota_exceeded"] = False
            all_files.append(f)

        # Hàng đợi quét các thư mục con lồng nhau: [(subfolder_id, subfolder_path, depth)]
        queue: List[Tuple[str, str, int]] = [
            (s_id, f"{root_name} / {s_name}", 1) for s_id, s_name in initial_subfolders
        ]
        folder_count += len(initial_subfolders)

        while queue:
            sub_id, sub_path, depth = queue.pop(0)
            if sub_id in visited_folders or depth > max_depth:
                continue
            visited_folders.add(sub_id)

            try:
                sub_title, sub_files, next_subs = self._parse_folder_page(sub_id)
                # Thêm file trong thư mục con này
                for sf in sub_files:
                    sf["path"] = f"{sub_path} / {sf['name']}"
                    sf["folder"] = sub_path
                    sf["size_bytes"] = 0
                    sf["size_formatted"] = "Không xác định"
                    sf["quota_exceeded"] = False
                    all_files.append(sf)

                # Thêm các thư mục con tiếp theo nếu còn độ sâu
                if depth < max_depth:
                    for n_id, n_name in next_subs:
                        if n_id not in visited_folders:
                            folder_count += 1
                            queue.append((n_id, f"{sub_path} / {n_name}", depth + 1))
            except Exception:
                # Nếu một thư mục con bị lỗi quyền truy cập thì bỏ qua thư mục đó, tiếp tục các thư mục khác
                continue

        # Tự động giải quyết UUID token cho các tệp tin trong thư mục để bypass cảnh báo virus file lớn
        # Dùng max 4 workers để tránh bị rate-limit Quota từ Google IP
        def _enrich_file(f):
            if f.get("kind") == "file":
                try:
                    direct_url, r_name, r_size, is_quota = self.resolve_direct_download_url(f["id"], "file", cookie=cookie)
                    f["download_url"] = direct_url
                    f["quota_exceeded"] = is_quota
                    if is_quota:
                        f["size_formatted"] = "⚠️ Đạt giới hạn 24h"
                    elif r_size:
                        f["size_formatted"] = r_size
                    if r_name and not r_name.startswith("file_") and not r_name.startswith("gdrive_file_"):
                        f["name"] = r_name
                except Exception:
                    pass
            f["smart_url"] = f"/api/gdrive/download/{f['id']}"
            return f

        if all_files:
            from concurrent.futures import ThreadPoolExecutor
            # Giảm max_workers xuống tối đa 4 để tránh kích hoạt Google Drive Quota rate limit
            max_w = min(4, max(1, len(all_files)))
            try:
                with ThreadPoolExecutor(max_workers=max_w) as executor:
                    all_files = list(executor.map(_enrich_file, all_files))
            except Exception:
                pass

        return {
            "root_name": root_name,
            "root_id": folder_id,
            "total_files": len(all_files),
            "total_folders": folder_count,
            "files": all_files
        }

    def scan_url(self, url: str, api_key: Optional[str] = None, max_depth: int = 10, cookie: Optional[str] = None) -> Dict[str, Any]:
        """
        Hàm tổng quát: Nhận vào link bất kỳ (Folder hoặc File), tự động nhận diện và quét.
        """
        res_id, res_type = self.parse_gdrive_url(url)
        if not res_id:
            raise ValueError("Đường dẫn Google Drive không hợp lệ. Vui lòng kiểm tra lại link Folder hoặc File.")

        if res_type == "folder":
            # Thư mục -> quét toàn bộ thư mục và nested folders
            result = self.scan_folder(res_id, api_key=api_key, max_depth=max_depth, cookie=cookie)
            # Nếu quét thư mục không ra file nào, thử kiểm tra xem có phải file đơn lẻ không
            if result.get("total_files", 0) == 0:
                try:
                    file_info = self.get_single_file_info(res_id, kind="file", cookie=cookie)
                    if file_info and not file_info["name"].startswith("gdrive_file_"):
                        return {
                            "root_name": file_info["name"],
                            "root_id": res_id,
                            "resource_type": "file",
                            "total_files": 1,
                            "total_folders": 0,
                            "files": [file_info]
                        }
                except Exception:
                    pass
            result["resource_type"] = "folder"
            return result
        else:
            # File đơn lẻ -> lấy thông tin file
            try:
                file_info = self.get_single_file_info(res_id, kind=res_type, cookie=cookie)
            except Exception as e:
                # Fallback thử quét như folder nếu lấy file thất bại
                try:
                    folder_res = self.scan_folder(res_id, api_key=api_key, max_depth=max_depth, cookie=cookie)
                    if folder_res.get("total_files", 0) > 0:
                        folder_res["resource_type"] = "folder"
                        return folder_res
                except Exception:
                    pass
                raise e

            return {
                "root_name": file_info["name"],
                "root_id": res_id,
                "resource_type": "file",
                "total_files": 1,
                "total_folders": 0,
                "files": [file_info]
            }


gdrive_service = GDriveService()

