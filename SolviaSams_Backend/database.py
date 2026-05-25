from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Date, Time, Text, Boolean
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
import uuid  # Thư viện tự tạo mã Code ngẫu nhiên
# Thêm chữ Float vào danh sách import này
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Date, Time, Text, Boolean, Float, JSON
# 1. KẾT NỐI DATABASE MYSQL
DATABASE_URL = "mysql+pymysql://root:@localhost:3306/sams_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ==========================================
# PHẦN 1: DỰ ÁN & CẤU HÌNH HỆ THỐNG
# ==========================================

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)

    # 1. Thông tin định danh
    project_code = Column(String(50), unique=True, index=True,
                          default=lambda: f"SAMS-{uuid.uuid4().hex[:6].upper()}")  # Tự sinh mã VD: SAMS-A1B2C3
    qr_code_data = Column(Text)  # Lưu dữ liệu mã QR để người khác quét

    # 2. Thông tin cơ bản
    project_name = Column(String(255), nullable=False)
    project_type = Column(String(50), default="Trường học")  # Trường học / Văn phòng
    school_name = Column(String(255))
    academic_year = Column(String(50))

    # 3. Cấu hình điểm danh chung
    session_type = Column(String(50))  # Sáng / Chiều / Sáng & Chiều

    # Lưu giờ giấc bằng kiểu Time để sau này AI/Server dễ dàng tính toán đi trễ/Về sớm
    morning_start_time = Column(Time, nullable=True)
    morning_end_time = Column(Time, nullable=True)
    afternoon_start_time = Column(Time, nullable=True)
    afternoon_end_time = Column(Time, nullable=True)
    morning_time = Column(String(100), nullable=True)
    afternoon_time = Column(String(100), nullable=True)

    attendance_mode = Column(String(100))  # Quy định chung / Theo từng ngày
    global_rule = Column(String(100))  # Giờ đầu / Giờ cuối / Cả đầu và cuối

    # Mối quan hệ
    classes = relationship("ClassRoom", back_populates="project", cascade="all, delete")
    staffs = relationship("Staff", back_populates="project", cascade="all, delete")


# ==========================================
# PHẦN 2: LỚP HỌC & THỜI KHÓA BIỂU
# ==========================================

class ClassRoom(Base):
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))

    # 1. Thông tin Lớp
    class_name = Column(String(100), nullable=False)
    semester = Column(String(50))  # Kỳ học (VD: Học kỳ 1)
    academic_year = Column(String(50))  # Năm học của lớp
    cohort = Column(String(50))  # Niên khóa (VD: 2024-2027)
    course_start_year = Column(Integer, default=2025)
    course_end_year = Column(Integer, default=2028)
    current_year_start = Column(Integer, default=2026)
    current_year_end = Column(Integer, default=2027)
    current_semester = Column(String(50), default="Học kỳ 1")
    teacher_id = Column(Integer, nullable=True)  # ID Giáo viên chủ nhiệm
    timetable = Column(JSON, nullable=True)

    # 2. Người quản lý (Giáo viên chủ nhiệm)
    # Nối với bảng Staff (Nhân sự/Giáo viên). Nếu null tức là lớp chưa có người quản lý
    manager_id = Column(Integer, ForeignKey("staffs.id"), nullable=True)

    # Mối quan hệ: Kéo Danh sách học sinh và Thời khóa biểu ra
    project = relationship("Project", back_populates="classes")
    students = relationship("Student", back_populates="classroom", cascade="all, delete")
    schedules = relationship("Schedule", back_populates="classroom", cascade="all, delete")


    # ==========================================
    # PHẦN 3: TÍCH HỢP TRẠNG THÁI XÉT DUYỆT VÀO NHÂN SỰ/HỌC SINH
    # ==========================================
    # (Bạn tìm đến bảng Staff và Student đã có, chèn thêm 1 dòng này vào)

    # Trong class Staff(Base):
    approval_status = Column(String(50), default="Đã duyệt")  # Trạng thái: "Chờ xét duyệt", "Đã duyệt", "Từ chối"

    # Trong class Student(Base):
    approval_status = Column(String(50),
                             default="Đã duyệt")  # Nếu Admin import Excel -> "Đã duyệt". Nếu học sinh tự quét QR -> "Chờ xét duyệt"
# ==========================================
# PHẦN 2: CON NGƯỜI (NHÂN SỰ & HỌC SINH)
# ==========================================

class Staff(Base):
    __tablename__ = "staffs"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)  # nullable=True để đăng ký không cần dự án

    # --- CÁC CỘT THÔNG TIN CÁ NHÂN ---
    avatar_url = Column(String(500))
    full_name = Column(String(150), nullable=False)
    gender = Column(String(20))
    dob = Column(String(50))
    religion = Column(String(100))
    hometown = Column(String(255))
    current_address = Column(String(255))
    phone = Column(String(20))
    facebook = Column(String(255))
    email = Column(String(150))
    role = Column(String(50))
    position = Column(String(150))
    degree = Column(String(150))
    graduated_from = Column(String(255))
    setting_language = Column(String(50), default="Tiếng Việt")
    setting_timezone = Column(String(100), default="UTC +07:00 (Hồ Chí Minh)")
    setting_theme_color = Column(String(50), default="0xFF448AFF")  # Màu Blue mặc định
    setting_font_scale = Column(Float, default=2.0)

    # --- CÁC CỘT DYNAMIC ---
    dynamic_1 = Column(String(255))
    dynamic_2 = Column(String(255))
    dynamic_3 = Column(String(255))

    # --- TÀI KHOẢN ---
    username = Column(String(100), unique=True, index=True)
    password = Column(String(255))

    project = relationship("Project", back_populates="staffs")
    schedules = relationship("Schedule", back_populates="teacher")


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"))

    # Cấu hình AI & Nhận diện
    student_code = Column(String(50), unique=True, index=True)  # Mã học sinh
    avatar_url = Column(String(500))  # File ảnh
    face_data = Column(Text)  # Dữ liệu mặt (Lưu chuỗi Vector/JSON từ AI)

    # Thông tin cơ bản
    full_name = Column(String(150), nullable=False)
    gender = Column(String(20))
    dob = Column(String(50))
    religion = Column(String(100))  # Tôn giáo
    hometown = Column(String(255))  # Quê quán
    current_address = Column(String(255))  # Nơi ở hiện tại
    parent_name = Column(String(100), nullable=True)
    email = Column(String(100), nullable=True)
    attendance_data = Column(JSON, nullable=True)

    # Liên hệ
    phone = Column(String(20))
    facebook = Column(String(255))
    email = Column(String(150))

    # Học tập
    status = Column(String(50), default="Đang học")  # Trạng thái (Đang học, Bảo lưu...)
    cohort = Column(String(50))  # Khóa học (VD: Khóa 2025)

    # Tài khoản
    username = Column(String(100), unique=True, index=True)
    password = Column(String(255))

    classroom = relationship("ClassRoom", back_populates="students")
    guardians = relationship("Guardian", back_populates="student", cascade="all, delete")
    attendances = relationship("AttendanceRecord", back_populates="student", cascade="all, delete")
    leaves = relationship("LeaveRequest", back_populates="student", cascade="all, delete")


class Guardian(Base):
    __tablename__ = "guardians"
    # NGƯỜI GIÁM HỘ (Tách riêng để 1 học sinh có thể có cả Ba và Mẹ)
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"))
    relation_type = Column(String(50))  # Quan hệ (Ba, Mẹ, Anh, Chị)
    full_name = Column(String(150))
    phone = Column(String(20))
    job = Column(String(150))

    student = relationship("Student", back_populates="guardians")


# ==========================================
# PHẦN 3: VẬN HÀNH (TKB, ĐIỂM DANH, NGHỈ PHÉP)
# ==========================================

class Schedule(Base):
    __tablename__ = "schedules"
    # THỜI KHÓA BIỂU
    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"))
    teacher_id = Column(Integer, ForeignKey("staffs.id"), nullable=True)  # Giáo viên dạy

    subject_name = Column(String(150))  # Tên môn
    day_of_week = Column(String(20))  # Thứ 2, Thứ 3...
    start_time = Column(Time)  # Giờ bắt đầu
    end_time = Column(Time)  # Giờ kết thúc

    classroom = relationship("ClassRoom", back_populates="schedules")
    teacher = relationship("Staff", back_populates="schedules")


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    # LỊCH SỬ ĐIỂM DANH & VI PHẠM (Chứa thông tin đi trễ, nghỉ không phép)
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"))

    date = Column(Date)  # Ngày điểm danh
    time_in = Column(Time, nullable=True)  # Giờ check-in thực tế
    subject_name = Column(String(150), nullable=True)  # Môn bị trễ/vắng (nếu điểm danh theo tiết)

    # Trạng thái: "Hợp lệ", "Đi trễ", "Vắng mặt"
    status = Column(String(50))

    student = relationship("Student", back_populates="attendances")


class LeaveRequest(Base):
    __tablename__ = "leave_requests"
    # NGHỈ CÓ PHÉP
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"))

    leave_mode = Column(String(50))  # "Nguyên ngày" hoặc "Theo tiết"
    start_date = Column(Date)  # Từ ngày
    end_date = Column(Date, nullable=True)  # Đến ngày (nếu nghỉ nhiều ngày)
    subject_name = Column(String(150), nullable=True)  # Tên môn (nếu chỉ xin nghỉ 1 tiết)

    reason = Column(Text)  # Lý do nghỉ
    is_approved = Column(Boolean, default=True)  # Trạng thái duyệt

    student = relationship("Student", back_populates="leaves")

class ProjectMember(Base):
    __tablename__ = "project_members"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    user_id = Column(Integer) # ID của người dùng
    role = Column(String(50), default="Khách") # Khách, Admin
    unit = Column(String(100), nullable=True)
    status = Column(String(50), default="Đang xét duyệt") # Đang xét duyệt, Hoạt động


# Hàm khởi tạo Database
def init_db():
    # CẢNH BÁO LÚC DEV: Lệnh drop_all() sẽ XÓA SẠCH database cũ để tạo lại cấu trúc mới này.
    # Khi phần mềm chạy thật, KHÔNG được dùng lệnh drop_all()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("Đã tái cấu trúc toàn bộ Cơ sở dữ liệu Chuẩn hóa SAMS thành công!")

    #uvicorn main:app --reload