from fastapi import FastAPI, Depends
from pydantic import BaseModel
from typing import List
from sqlalchemy.orm import Session
from database import init_db, SessionLocal, Project, ClassRoom, Student
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Depends, File, UploadFile # Thêm File, UploadFile
from fastapi.staticfiles import StaticFiles # Thêm thư viện cấp quyền xem ảnh
import os
import shutil

# Khởi tạo ứng dụng
app = FastAPI(title="SAMS Backend API")
# Tạo thư mục chứa ảnh nếu chưa có
os.makedirs("static/avatars", exist_ok=True)

# Cấp quyền truy cập công khai cho thư mục static
app.mount("/static", StaticFiles(directory="static"), name="static")

# CẤP QUYỀN CORS: Bắt buộc phải có để App Flutter không bị chặn khi gửi dữ liệu sang
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tự động tạo bảng nếu chưa có
init_db()


# Hàm mở kết nối an toàn tới MySQL
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =====================================================================
# 1. ĐỊNH NGHĨA CẤU TRÚC DỮ LIỆU SẼ NHẬN TỪ FLUTTER (Pydantic Models)
# =====================================================================
class StudentCreate(BaseModel):
    stt: str
    name: str
    gender: str
    dob: str
    hometown: str
    phone: str
    username: str
    password: str


class ClassCreate(BaseModel):
    class_name: str
    students: List[StudentCreate] = []
    timetable: list = []


class ProjectCreate(BaseModel):
    project_name: str
    school_name: str
    academic_year: str
    project_type: str
    session_type: str
    attendance_mode: str
    global_rule: str
    classes: List[ClassCreate] = []
    user_id: int


# =====================================================================
# 2. XÂY DỰNG API NHẬN DỮ LIỆU VÀ LƯU VÀO MYSQL (Xử lý hàng loạt)
# =====================================================================
@app.post("/api/create-project")
def create_project(project_data: ProjectCreate, db: Session = Depends(get_db)):
    try:
        # BƯỚC 1: Lưu thông tin Dự Án
        new_project = Project(
            project_name=project_data.project_name,
            school_name=project_data.school_name,
            academic_year=project_data.academic_year,
            project_type=project_data.project_type,
            session_type=project_data.session_type,
            attendance_mode=project_data.attendance_mode,
            global_rule=project_data.global_rule
        )
        db.add(new_project)
        db.commit()
        db.refresh(new_project)

        # BƯỚC 2: GHI DANH SUPER ADMIN NGAY SAU KHI TẠO DỰ ÁN (ĐÃ ĐƯA RA NGOÀI VÒNG LẶP)
        from database import ProjectMember
        owner = ProjectMember(
            project_id=new_project.id,
            user_id=project_data.user_id,  # Lấy ID người dùng gửi lên
            role="Super Admin",
            status="Hoạt động"
        )
        db.add(owner)
        db.commit()

        # BƯỚC 3: Lưu các Lớp học vào bảng `classes`
        for cls_data in project_data.classes:
            new_class = ClassRoom(
                project_id=new_project.id,
                class_name=cls_data.class_name,
                timetable=cls_data.timetable
            )
            db.add(new_class)
            db.commit()
            db.refresh(new_class)

            for std_data in cls_data.students:
                new_student = Student(
                    class_id=new_class.id,
                    student_code=std_data.stt,
                    full_name=std_data.name,
                    gender=std_data.gender,
                    dob=std_data.dob,
                    hometown=std_data.hometown,
                    phone=std_data.phone,
                    username=std_data.username,
                    password=std_data.password
                )
                db.add(new_student)
            db.commit()

        return {
            "status": "success",
            "message": "Tuyệt vời! Đã lưu Dự án, Lớp học và nạp toàn bộ danh sách Excel vào MySQL!",
            "project_id": new_project.id
        }

    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Lỗi hệ thống: {str(e)}"}


# =====================================================================
# 4. API ĐĂNG KÝ TÀI KHOẢN QUẢN TRỊ (REGISTER)
# =====================================================================

class UserRegister(BaseModel):
    full_name: str
    email: str
    phone: str
    password: str
    role: str


@app.post("/api/register")
def register_user(user_data: UserRegister, db: Session = Depends(get_db)):
    from database import Staff

    try:
        # 1. Kiểm tra xem Email đã tồn tại chưa
        existing_user = db.query(Staff).filter(Staff.email == user_data.email).first()
        if existing_user:
            return {"status": "error", "message": "Email này đã được đăng ký trong hệ thống!"}

        # 2. Tạo tài khoản mới (KHÔNG CẦN DUYỆT GÌ CẢ)
        new_user = Staff(
            full_name=user_data.full_name,
            email=user_data.email,
            phone=user_data.phone,
            password=user_data.password,
            role=user_data.role,
            username=user_data.email  # Lấy email làm username đăng nhập luôn cho tiện
        )

        db.add(new_user)
        db.commit()

        return {"status": "success", "message": "Tuyệt vời! Đăng ký tài khoản thành công."}

    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Lỗi Server: {str(e)}"}


# =====================================================================
# 5. API ĐĂNG NHẬP (LOGIN)
# =====================================================================

class UserLogin(BaseModel):
    username: str  # Có thể là Email hoặc Tên đăng nhập
    password: str
    role: str


@app.post("/api/login")
def login_user(login_data: UserLogin, db: Session = Depends(get_db)):
    from database import Staff

    try:
        # 1. Tìm user trong Database theo Email (hoặc username) và Quyền truy cập
        user = db.query(Staff).filter(
            (Staff.email == login_data.username) | (Staff.username == login_data.username),
            Staff.role == login_data.role
        ).first()

        # 2. Chốt chặn 1: Không tìm thấy tài khoản hoặc chọn sai quyền
        if not user:
            return {"status": "error",
                    "message": f"Tài khoản không tồn tại hoặc bạn không có quyền '{login_data.role}'!"}

        # 3. Chốt chặn 2: Sai mật khẩu
        if user.password != login_data.password:
            return {"status": "error", "message": "Mật khẩu không chính xác. Vui lòng thử lại!"}

        # 4. THÀNH CÔNG: Trả về thông tin User để Flutter lưu lại (Làm phiên đăng nhập)
        return {
            "status": "success",
            "message": f"Đăng nhập thành công! Chào mừng {user.full_name}.",
            "data": {
                "user_id": user.id,
                "full_name": user.full_name,
                "role": user.role,

                # BỔ SUNG 4 DÒNG NÀY ĐỂ FLUTTER BIẾT MÀ HIỂN THỊ
                "setting_language": user.setting_language or "Tiếng Việt",
                "setting_timezone": user.setting_timezone or "UTC +07:00 (Hồ Chí Minh)",
                "setting_theme_color": user.setting_theme_color or "0xFF448AFF",
                "setting_font_scale": user.setting_font_scale if user.setting_font_scale is not None else 2.0
            }
        }

    except Exception as e:
        return {"status": "error", "message": f"Lỗi Server: {str(e)}"}

# =====================================================================
# API CHO QUẢN LÝ TÀI KHOẢN (ACCOUNT SETTINGS)
# =====================================================================
# =====================================================================
# API CHO QUẢN LÝ TÀI KHOẢN (ACCOUNT SETTINGS)
# =====================================================================
class UserUpdate(BaseModel):
    full_name: str
    dob: str
    hometown: str
    current_address: str
    religion: str
    email: str
    phone: str
    facebook: str
    position: str = ""  # Từ khóa chuẩn xác cho Chức vụ
    degree: str = ""  # Từ khóa chuẩn xác cho Bằng cấp
    graduated_from: str = ""
    dynamic_1: str
    dynamic_2: str
    dynamic_3: str


# 1. Cổng lấy thông tin (GET)
@app.get("/api/users/{user_id}")
def get_user_profile(user_id: int, db: Session = Depends(get_db)):
    from database import Staff

    user = db.query(Staff).filter(Staff.id == user_id).first()
    if not user:
        return {"status": "error", "message": "Không tìm thấy người dùng trong hệ thống!"}

    return {
        "status": "success",
        "data": {
            "avatar_url": user.avatar_url or "",
            "full_name": user.full_name or "",
            "dob": user.dob or "",
            "hometown": user.hometown or "",
            "current_address": user.current_address or "",
            "religion": user.religion or "",
            "email": user.email or "",
            "phone": user.phone or "",
            "facebook": user.facebook or "",

            # ĐỔI: Trả về cả Role (Quyền) và Position (Chức vụ)
            "role": user.role or "",
            "position": user.position or "",

            "degree": user.degree or "",
            "graduated_from": user.graduated_from or "",
            "dynamic_1": user.dynamic_1 or "",
            "dynamic_2": user.dynamic_2 or "",
            "dynamic_3": user.dynamic_3 or ""
        }
    }


# 2. Cổng lưu thông tin (PUT)
@app.put("/api/users/{user_id}")
def update_user_profile(user_id: int, user_data: UserUpdate, db: Session = Depends(get_db)):
    from database import Staff
    user = db.query(Staff).filter(Staff.id == user_id).first()
    if not user:
        return {"status": "error", "message": "Không tìm thấy tài khoản"}

    try:
        user.full_name = user_data.full_name
        user.dob = user_data.dob
        user.hometown = user_data.hometown
        user.current_address = user_data.current_address
        user.religion = user_data.religion

        user.email = user_data.email
        user.username = user_data.email

        user.phone = user_data.phone
        user.facebook = user_data.facebook

        # ĐỔI: Lưu Chức vụ công tác vào cột 'position', KHÔNG CHẠM VÀO 'role'
        user.position = user_data.position

        user.degree = user_data.degree
        user.graduated_from = user_data.graduated_from
        user.dynamic_1 = user_data.dynamic_1
        user.dynamic_2 = user_data.dynamic_2
        user.dynamic_3 = user_data.dynamic_3
        db.commit()
        return {"status": "success", "message": "Đã lưu thành công!"}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}

# =====================================================================
# API UPLOAD ẢNH ĐẠI DIỆN
# =====================================================================
@app.post("/api/users/{user_id}/avatar")
def upload_avatar(user_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    from database import Staff
    user = db.query(Staff).filter(Staff.id == user_id).first()
    if not user:
        return {"status": "error", "message": "Không tìm thấy tài khoản"}

    try:
        # Tạo đường dẫn lưu file: Ví dụ -> static/avatars/1_hinhanh.jpg
        file_location = f"static/avatars/{user_id}_{file.filename}"

        # Lưu file vật lý vào ổ cứng Server
        with open(file_location, "wb+") as file_object:
            shutil.copyfileobj(file.file, file_object)

        # Cập nhật đường dẫn vào Database
        user.avatar_url = f"/{file_location}"
        db.commit()

        return {"status": "success", "message": "Cập nhật ảnh thành công!", "avatar_url": user.avatar_url}
    except Exception as e:
        return {"status": "error", "message": f"Lỗi lưu ảnh: {str(e)}"}


# =====================================================================
# API CÀI ĐẶT HỆ THỐNG (LƯU CẤU HÌNH & ĐỔI MẬT KHẨU)
# =====================================================================

class SettingsUpdate(BaseModel):
    language: str
    timezone: str
    theme_color: str
    font_scale: float


class PasswordUpdate(BaseModel):
    old_password: str
    new_password: str


# 1. API Lưu cài đặt giao diện
@app.put("/api/users/{user_id}/settings")
def update_user_settings(user_id: int, settings: SettingsUpdate, db: Session = Depends(get_db)):
    from database import Staff
    user = db.query(Staff).filter(Staff.id == user_id).first()
    if not user:
        return {"status": "error", "message": "Không tìm thấy tài khoản"}

    try:
        user.setting_language = settings.language
        user.setting_timezone = settings.timezone
        user.setting_theme_color = settings.theme_color
        user.setting_font_scale = settings.font_scale
        db.commit()
        return {"status": "success", "message": "Đã lưu cài đặt hệ thống!"}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}


# 2. API Đổi mật khẩu
@app.put("/api/users/{user_id}/password")
def change_user_password(user_id: int, pass_data: PasswordUpdate, db: Session = Depends(get_db)):
    from database import Staff
    user = db.query(Staff).filter(Staff.id == user_id).first()
    if not user:
        return {"status": "error", "message": "Không tìm thấy tài khoản"}

    try:
        # Kiểm tra mật khẩu cũ có đúng không
        if user.password != pass_data.old_password:
            return {"status": "error", "message": "Mật khẩu hiện tại không chính xác!"}

        # Lưu mật khẩu mới
        user.password = pass_data.new_password
        db.commit()
        return {"status": "success", "message": "Cập nhật mật khẩu thành công!"}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}


# =====================================================================
# API LẤY DANH SÁCH DỰ ÁN ĐỂ HIỂN THỊ LÊN KHO
# =====================================================================
@app.get("/api/projects")
def get_all_projects(db: Session = Depends(get_db)):
    from database import Project
    # Lấy toàn bộ dự án từ Database
    projects = db.query(Project).all()

    data = []
    for p in projects:
        data.append({
            "id": p.id,
            "project_name": p.project_name,
            "project_type": p.project_type,
            "project_code": p.project_code,
            "status": "Hoạt động"  # Mặc định dự án mới tạo là Hoạt động
        })

    return {"status": "success", "data": data}


# =====================================================================
# API LẤY CHI TIẾT 1 DỰ ÁN
# =====================================================================
@app.get("/api/projects/{project_id}")
def get_project_detail(project_id: int, db: Session = Depends(get_db)):
    from database import Project, ClassRoom, Student, ProjectMember  # ---> KHAI BÁO THÊM ProjectMember
    project = db.query(Project).filter(Project.id == project_id).first()

    if not project:
        return {"status": "error", "message": "Không tìm thấy dự án"}

    # Đếm số lượng học sinh thực tế
    total_students = db.query(Student).join(ClassRoom).filter(ClassRoom.project_id == project_id).count()

    # ---> BỔ SUNG: ĐẾM TỔNG NHÂN SỰ (Những người có trạng thái Hoạt động)
    total_staff = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.status == "Hoạt động"
    ).count()

    return {
        "status": "success",
        "data": {
            "project_name": project.project_name or "",
            "school_name": project.school_name or "",
            "academic_year": project.academic_year or "",
            "session_type": project.session_type or "",
            "attendance_mode": project.attendance_mode or "",
            "global_rule": project.global_rule or "",
            "project_code": project.project_code or "",
            "morning_time": project.morning_time or "",
            "afternoon_time": project.afternoon_time or "",

            # TRẢ VỀ CÁC CHỈ SỐ THỐNG KÊ THẬT
            "total_students": total_students,
            "total_staff": total_staff,  # ---> ĐÃ THAY SỐ 0 THÀNH BIẾN ĐẾM THẬT
            "late_rate": "0.0%",
            "absent_rate": "0.0%",

            "chart_data": [
                {'day': 'T2', 'ok': 0, 'late': 0}, {'day': 'T3', 'ok': 0, 'late': 0},
                {'day': 'T4', 'ok': 0, 'late': 0}, {'day': 'T5', 'ok': 0, 'late': 0},
                {'day': 'T6', 'ok': 0, 'late': 0}, {'day': 'T7', 'ok': 0, 'late': 0}
            ]
        }
    }


# =====================================================================
# API CẬP NHẬT CẤU HÌNH DỰ ÁN
# =====================================================================
class ProjectUpdate(BaseModel):
    project_name: str
    school_name: str
    academic_year: str
    session_type: str
    attendance_mode: str
    global_rule: str
    morning_time: str  # ---> BỔ SUNG
    afternoon_time: str


@app.put("/api/projects/{project_id}")
def update_project_detail(project_id: int, project_data: ProjectUpdate, db: Session = Depends(get_db)):
    from database import Project
    project = db.query(Project).filter(Project.id == project_id).first()

    if not project:
        return {"status": "error", "message": "Không tìm thấy dự án!"}

    try:
        # Cập nhật tất cả thông tin (Trừ project_type là không đổi)
        project.project_name = project_data.project_name
        project.school_name = project_data.school_name
        project.academic_year = project_data.academic_year
        project.session_type = project_data.session_type
        project.attendance_mode = project_data.attendance_mode
        project.global_rule = project_data.global_rule
        project.morning_time = project_data.morning_time
        project.afternoon_time = project_data.afternoon_time
        db.commit()
        return {"status": "success", "message": "Lưu cấu hình thành công!"}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}


# =====================================================================
# API LẤY CHI TIẾT 1 LỚP HỌC (KÈM HỌC SINH VÀ THỜI KHÓA BIỂU)
# =====================================================================
@app.get("/api/classes/{class_id}")
def get_class_detail(class_id: int, db: Session = Depends(get_db)):
    from database import ClassRoom, Student, Staff
    classroom = db.query(ClassRoom).filter(ClassRoom.id == class_id).first()
    if not classroom:
        return {"status": "error", "message": "Không tìm thấy lớp học"}

    # Lấy thông tin GVCN (Nếu có)
    teacher = db.query(Staff).filter(Staff.id == classroom.teacher_id).first() if classroom.teacher_id else None

    # Lấy danh sách Học sinh
    students = db.query(Student).filter(Student.class_id == class_id).all()
    student_list = []

    # Khuôn điểm danh mặc định nếu học sinh chưa có dữ liệu
    default_attendance = {
        f"{classroom.current_year_start}-{classroom.current_year_end}": {
            classroom.current_semester: {"lateCount": 0, "absentCount": 0, "excusedCount": 0, "history": []}
        }
    }

    for st in students:
        student_list.append({
            "id": st.student_code or "Chưa cấp",
            "name": st.full_name or "Không tên",
            "gender": st.gender or "Nam",
            "dob": st.dob or "Chưa cập nhật",
            "parent": st.parent_name or "Chưa cập nhật",
            "phone": st.phone or "Chưa cập nhật",
            "email": st.email or "hs@edu.vn",
            "attendance": st.attendance_data or default_attendance
        })

    # Đóng gói thông tin GVCN
    teacher_info = {}
    if teacher:
        teacher_info = {
            "avatar_url": teacher.avatar_url or "",
            "name": teacher.full_name,
            "email": teacher.email,
            "role": "Giáo viên chủ nhiệm",
            "dob": teacher.dob,
            "phone": teacher.phone,
            "hometown": teacher.hometown,
            "religion": teacher.religion,
            "current_address": teacher.current_address,
            "position": teacher.position,
            "degree": teacher.degree,
            "school": teacher.graduated_from,
            "dynamic_1": teacher.dynamic_1 or "",
            "dynamic_2": teacher.dynamic_2 or "",
            "dynamic_3": teacher.dynamic_3 or ""
        }
    else:
        # Nếu chưa phân công thì chỉ trả về tên để Flutter nhận diện
        teacher_info = {"name": "Chưa phân công"}

    return {
        "status": "success",
        "data": {
            "class_name": classroom.class_name,
            "course_start_year": classroom.course_start_year,
            "course_end_year": classroom.course_end_year,
            "current_year_start": classroom.current_year_start,
            "current_year_end": classroom.current_year_end,
            "current_semester": classroom.current_semester,
            "timetable": classroom.timetable or [],  # Trả về list rỗng nếu chưa có TKB
            "teacher": teacher_info,
            "students": student_list
        }
    }


# =====================================================================
# API LẤY DANH SÁCH LỚP HỌC THEO DỰ ÁN (HIỂN THỊ MENU)
# =====================================================================
@app.get("/api/projects/{project_id}/classes")
def get_project_classes(project_id: int, db: Session = Depends(get_db)):
    from database import ClassRoom
    # Tìm tất cả các lớp có project_id trùng khớp
    classes = db.query(ClassRoom).filter(ClassRoom.project_id == project_id).all()

    data = []
    for c in classes:
        data.append({
            "id": c.id,
            "class_name": c.class_name
        })

    return {"status": "success", "data": data}


# =====================================================================
# API CẬP NHẬT CẤU HÌNH LỚP VÀ THỜI KHÓA BIỂU
# =====================================================================
class ClassUpdate(BaseModel):
    class_name: str
    course_start_year: int
    course_end_year: int
    current_year_start: int
    current_year_end: int
    current_semester: str
    timetable: list


@app.put("/api/classes/{class_id}")
def update_class_detail(class_id: int, class_data: ClassUpdate, db: Session = Depends(get_db)):
    from database import ClassRoom
    classroom = db.query(ClassRoom).filter(ClassRoom.id == class_id).first()
    if not classroom:
        return {"status": "error", "message": "Không tìm thấy lớp học"}

    try:
        classroom.class_name = class_data.class_name
        classroom.course_start_year = class_data.course_start_year
        classroom.course_end_year = class_data.course_end_year
        classroom.current_year_start = class_data.current_year_start
        classroom.current_year_end = class_data.current_year_end
        classroom.current_semester = class_data.current_semester
        classroom.timetable = class_data.timetable  # Lưu thời khóa biểu mới
        db.commit()
        return {"status": "success"}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}


# =====================================================================
# API THAM GIA DỰ ÁN BẰNG MÁ
# =====================================================================
class JoinProjectRequest(BaseModel):
    project_code: str
    user_id: int


@app.post("/api/projects/join")
def join_project(request: JoinProjectRequest, db: Session = Depends(get_db)):
    from database import Project, ProjectMember
    project = db.query(Project).filter(Project.project_code == request.project_code).first()

    if not project:
        return {"status": "error", "message": "Mã dự án không tồn tại!"}

    existing = db.query(ProjectMember).filter(ProjectMember.project_id == project.id, ProjectMember.user_id == request.user_id).first()
    if existing:
        return {"status": "error", "message": "Bạn đã gửi yêu cầu gia nhập dự án này rồi!"}

    new_member = ProjectMember(project_id=project.id, user_id=request.user_id, role="Khách truy cập", status="Đang xét duyệt")
    db.add(new_member)
    db.commit()
    return {
        "status": "success",
        "message": "Đã gửi yêu cầu. Vui lòng chờ Quản trị viên duyệt!",
        "data": {
            "id": project.id, "project_name": project.project_name, "project_type": project.project_type,
            "role": "Khách truy cập", "status": "Đang xét duyệt", "is_owner": False
        }
    }

# =====================================================================
# 2. API KÉO DANH SÁCH DỰ ÁN (CỦA MÌNH + DỰ ÁN XIN GIA NHẬP)
# =====================================================================
@app.get("/api/users/{user_id}/projects")
def get_user_projects(user_id: int, db: Session = Depends(get_db)):
    from database import Project, ProjectMember
    memberships = db.query(ProjectMember).filter(ProjectMember.user_id == user_id).all()

    data = []
    for m in memberships:
        p = db.query(Project).filter(Project.id == m.project_id).first()
        if p:
            data.append({
                "id": p.id, "project_name": p.project_name, "project_type": p.project_type,
                "role": m.role, "status": m.status, "is_owner": m.role == "Super Admin"
            })
    return {"status": "success", "data": data}

# =====================================================================
# API QUẢN LÝ THÀNH VIÊN DỰ ÁN (XÉT DUYỆT, CẤP QUYỀN, XÓA)
# =====================================================================
from typing import Optional

@app.get("/api/projects/{project_id}/members")
def get_project_members(project_id: int, db: Session = Depends(get_db)):
    from database import ProjectMember, Staff # ---> ĐÃ FIX THÀNH STAFF
    members = db.query(ProjectMember).filter(ProjectMember.project_id == project_id).all()

    active_admins = []
    active_managers = []
    pending_requests = []

    for m in members:
        user = db.query(Staff).filter(Staff.id == m.user_id).first() # ---> ĐÃ FIX THÀNH STAFF
        if not user: continue

        member_data = {
            "id": m.id,
            "user_id": user.id,
            "name": user.full_name,
            "email": user.email,
            "role": m.role,
            "unit": m.unit,
            "status": m.status,

            # ---> BỔ SUNG LẤY THÊM THÔNG TIN CÁ NHÂN TỪ BẢNG STAFF:
            "avatar_url": user.avatar_url or "",
            "dob": user.dob,
            "phone": user.phone,
            "hometown": user.hometown,
            "current_address": user.current_address,
            "religion": user.religion,
            "facebook": user.facebook,
            "position": user.position,
            "degree": user.degree,
            "school": user.graduated_from,
            "dynamic_1": user.dynamic_1 or "",
            "dynamic_2": user.dynamic_2 or "",
            "dynamic_3": user.dynamic_3 or ""
        }
        if m.status == "Đang xét duyệt":
            pending_requests.append(member_data)
        elif m.status == "Hoạt động":
            if m.role == "Super Admin" or m.role == "Admin": active_admins.append(member_data)
            else: active_managers.append(member_data)

    return {"status": "success", "data": {"admins": active_admins, "managers": active_managers, "pending": pending_requests}}

class MemberUpdateRequest(BaseModel):
    status: str
    role: str
    unit: Optional[str] = None


# 1. API Kéo danh sách thành viên trong dự án
def get_user_projects(user_id: int, db: Session = Depends(get_db)):
    from database import Project, ProjectMember
    memberships = db.query(ProjectMember).filter(ProjectMember.user_id == user_id).all()

    data = []
    for m in memberships:
        p = db.query(Project).filter(Project.id == m.project_id).first()
        if p:
            data.append({
                "id": p.id,
                "project_name": p.project_name,
                "project_type": p.project_type,
                "role": m.role,
                "status": m.status,
                "is_owner": m.role == "Super Admin"
            })

    return {"status": "success", "data": data}



@app.put("/api/members/{member_id}")
def update_project_member(member_id: int, request: MemberUpdateRequest, db: Session = Depends(get_db)):
    from database import ProjectMember, ClassRoom  # ---> KHAI BÁO THÊM BẢNG LỚP HỌC
    member = db.query(ProjectMember).filter(ProjectMember.id == member_id).first()
    if not member: return {"status": "error", "message": "Không tìm thấy thành viên!"}

    member.status = request.status
    member.role = request.role
    member.unit = request.unit

    # ---> LOGIC MỚI: NẾU GÁN LÀM QUẢN LÝ LỚP (UNIT MANAGER) THÌ CHÈN ID VÀO LỚP HỌC ĐÓ
    if request.role == 'Unit Manager' and request.unit:
        # Tìm lớp học trong dự án này có tên khớp với tên lớp vừa gán
        target_class = db.query(ClassRoom).filter(
            ClassRoom.project_id == member.project_id,
            ClassRoom.class_name == request.unit
        ).first()

        if target_class:
            target_class.teacher_id = member.user_id  # Chốt sổ: Gắn ID giáo viên vào lớp!

    db.commit()
    return {"status": "success"}

# 3. API Xóa / Từ chối thành viên
@app.delete("/api/members/{member_id}")
def delete_project_member(member_id: int, db: Session = Depends(get_db)):
    from database import ProjectMember
    member = db.query(ProjectMember).filter(ProjectMember.id == member_id).first()
    if member:
        db.delete(member)
        db.commit()
    return {"status": "success"}

