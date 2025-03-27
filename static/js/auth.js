document.addEventListener("DOMContentLoaded", function () {
    const signupForm = document.getElementById("signupForm");
    if (signupForm) {
        signupForm.addEventListener("submit", async function (e) {
            e.preventDefault();

            const name = document.getElementById("signupName").value;
            const email = document.getElementById("signupEmail").value;
            const password = document.getElementById("signupPassword").value;
            const userType = window.location.pathname.includes("signup-student") ? "student" : "tutor";

            try {
                const response = await fetch("/api/signup", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ name, email, password, userType }),
                });

                const data = await response.json();
                alert(data.msg);

                if (response.ok) {
                    window.location.href = "/login-page";
                }
            } catch (error) {
                console.error("Signup error:", error);
            }
        });
    }

    const signupStudentForm = document.getElementById("signupStudentForm");
    if (signupStudentForm) {
        signupStudentForm.addEventListener("submit", async function (e) {
            e.preventDefault();

            console.log("Student Signup Submitted!");
            const name = document.getElementById("signupName").value;
            const email = document.getElementById("signupEmail").value;
            const password = document.getElementById("signupPassword").value;

            try {
                const response = await fetch("/api/signup", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ name, email, password, userType: "student" }),
                });

                const data = await response.json();
                alert(data.msg);

                if (response.ok) {
                    window.location.href = "/login-page";
                }
            } catch (error) {
                console.error("Student signup error:", error);
            }
        });
    }

    const loginForm = document.getElementById("loginForm");
    if (loginForm) {
        loginForm.addEventListener("submit", async function (e) {
            e.preventDefault();

            const email = document.getElementById("loginEmail").value;
            const password = document.getElementById("loginPassword").value;

            try {
                const response = await fetch("/api/login", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ email, password }),
                });

                const data = await response.json();

                if (response.ok) {
                    localStorage.setItem("userType", data.role);
                    
                    if (data.role === "tutor") {
                        localStorage.setItem("tutor_id", data.tutor_id);
                        if (data.firstLogin) {
                            window.location.href = "/tutor/settings";
                        } else {
                            window.location.href = "/dashboard/tutor";
                        }
                    } else if (data.role === "student") {
                        localStorage.setItem("student_id", data.student_id);
                        if (data.firstLogin) {
                            window.location.href = "/student/settings";
                        } else {
                            window.location.href = "/dashboard-student";
                        }
                    }
                } else {
                    alert(data.msg);
                }
            } catch (error) {
                console.error("Login error:", error);
            }
        });
    }
});
