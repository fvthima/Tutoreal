document.addEventListener("DOMContentLoaded", function () {
    const userType = localStorage.getItem("userType");

    if (userType === "tutor") {
        const tutorId = localStorage.getItem("tutor_id");
        if (tutorId) {
            document.querySelectorAll("a").forEach(link => {
                if (link.href.includes("tutor_id=")) {
                    link.href = link.href.replace(/tutor_id=\d+/, `tutor_id=${tutorId}`);
                }
            });
        } else {
            console.error("Tutor ID not found in localStorage");
        }
    } else if (userType === "student") {
        const studentId = localStorage.getItem("student_id");
        if (studentId) {
            document.querySelectorAll("a").forEach(link => {
                if (link.href.includes("student_id=")) {
                    link.href = link.href.replace(/student_id=\d+/, `student_id=${studentId}`);
                }
            });
        } else {
            console.error("Student ID not found in localStorage");
        }
    }
});
