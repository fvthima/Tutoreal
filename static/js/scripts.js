(function ($) {
    $(document).ready(function () {
        jQuery(".scrolltotop").click(function () {
            jQuery("html").animate({ scrollTop: "0px" }, 400);
            return false;
        });

        jQuery(window).scroll(function () {
            var upto = jQuery(window).scrollTop();
            if (upto > 10) {
                jQuery(".main-header ").addClass("menu-sticky");
            } else {
                jQuery(".scrolltotop").removeClass("menu-sticky");
            }
        });

        // landing page js

        jQuery(".getstart-btn button").click(function () {
            jQuery(".landing-action-group").addClass("activate");
        });

        jQuery(document).ready(function () {
            function toggleSidebarHover() {
                if (jQuery(window).width() >= 992) {
                    jQuery(".sidebar-area").removeClass("open-menu");
                    jQuery(".sidebar-area").hover(function () {
                        jQuery(this).toggleClass("open-menu");
                        jQuery(".main-area").toggleClass("open-sidebar");
                    });
                } else {
                    jQuery(".sidebar-area").off("mouseenter mouseleave");
                    jQuery(".sidebar-area").addClass("open-menu");
                }
            }

            toggleSidebarHover();

            jQuery(window).resize(function () {
                toggleSidebarHover();
            });
        });

        jQuery(document).click(function (event) {
            if (!jQuery(event.target).closest(".sidebar-area, .menu-toggle-btn").length) {
                jQuery(".sidebar-area").removeClass("nav-active");
                jQuery(".overlay").removeClass("overlay-active");
            }
        });

        jQuery(".menu-toggle-btn button").click(function (event) {
            event.stopPropagation();
            jQuery(".sidebar-area").addClass("nav-active");
            jQuery(".overlay").addClass("overlay-active");
        });
        jQuery(".menu-close-toggle").click(function () {
            jQuery(".sidebar-area").removeClass("nav-active");
            jQuery(".overlay").removeClass("overlay-active");
        });

        // right profile js start hare
        jQuery(".right-profile-full").click(function (event) {
            jQuery(this).toggleClass("dropdown-active");
            jQuery(".profile-action-nav").slideToggle("fast");
            event.stopPropagation();
        });

        jQuery(document).click(function (event) {
            if (!jQuery(".right-profile-full").is(event.target) && jQuery(".right-profile-full").has(event.target).length === 0) {
                jQuery(".right-profile-full").removeClass("dropdown-active");
                jQuery(".profile-action-nav").slideUp("fast");
            }
        });

        $(".profile-action-nav a").click(function (event) {
            event.stopPropagation();
        });

        // your progress progressbar

        var options = {
            startAngle: -1.55,
            size: 150,
            value: 0.75,
            fill: { gradient: ["#FA00FF00", "#0077FF"] },
            thickness: 13,
        };

        $(".circle1 .bar1").circleProgress({
            startAngle: options.startAngle,
            size: options.size,
            value: options.value,
            fill: options.fill,
            thickness: options.thickness,
        });
        $(".circle2 .bar2").circleProgress({
            startAngle: options.startAngle,
            size: options.size,
            value: 0.91,
            fill: { gradient: ["#66BC22", "#0077FF"] },
            thickness: options.thickness,
        });
        $(".circle3 .bar3").circleProgress({
            startAngle: options.startAngle,
            size: options.size,
            value: 0.25,
            fill: "#0077FF",
            thickness: options.thickness,
        });

        // recommended totur match circle
        $(".circle4 .bar4").circleProgress({
            startAngle: options.startAngle,
            size: options.size,
            value: 0.91,
            fill: { gradient: ["#8FFF00", "#0077FF"] },
            thickness: options.thickness,
        });
        $(".circle5 .bar5").circleProgress({
            startAngle: options.startAngle,
            size: options.size,
            value: 0.95,
            fill: { gradient: ["#8FFF00", "#0077FF"] },
            thickness: options.thickness,
        });

        // earning chart

        $(".circle6 .bar6").circleProgress({
            startAngle: options.startAngle,
            size: options.size,
            value: 0.8,
            fill: { gradient: ["#20C997", "#20C997"] },
            thickness: 30,
            emptyFill: "#fff",
        });

        // tutor fide page progress

        $(".tutor-circle .tutor-bar").circleProgress({
            startAngle: options.startAngle,
            size: options.size,
            value: 0.91,
            fill: { gradient: ["#8FFF00", "#0077FF"] },
            thickness: options.thickness,
        });

        var scoreValue = $('.tutor-circle2').data('score');

        $(".tutor-circle2 .tutor-bar2")
        .circleProgress({
            startAngle: options.startAngle, 
            size: 240,
            value: scoreValue,  
            fill: { gradient: ["#8FFF00", "#0077FF"] },
            thickness: 25,
        })
        .on("circle-animation-progress", function (event, progress, stepValue) {
            $(this).parent().find("span").text(String((stepValue * 100).toFixed(0)) + "%");
        });

        $(".circle .bar canvas").css({
        transform: "scale(0.8)",
        transformOrigin: "center",
        });


        $(".student-sessions")
        .circleProgress({
            startAngle: options.startAngle,
            size: 240,
            value: 1.00, 
            fill: { gradient: ["#8FFF00", "#0077FF"] },
            thickness: 25,
        })
        .on("circle-animation-progress", function (event, progress) {
            var currentCount = Math.round(progress * totalSessions);
            $(this).parent().find("span").text(currentCount);

        $(".circle .bar canvas").css({
            transform: "scale(0.8)",
            transformOrigin: "center",
        });
        });


    });
})(jQuery);

//   js code for others pages

$(document).ready(function () {
    $(".create-slots input")
        .focus(function () {
            $(this).closest(".create-slots").addClass("slot-active");
        })
        .blur(function () {
            $(this).closest(".create-slots").removeClass("slot-active");
        });

    // notification page js

    $(".notification-tab-nav a").click(function (e) {
        e.preventDefault();

        $(".notification-tab-nav a").removeClass("active");
        $(".notify-tab-content").removeClass("active");

        $(this).addClass("active");
        $($(this).attr("href")).addClass("active");
    });

    // massage page js start hare

    jQuery(".default-all-massage").click(function (event) {
        event.stopPropagation();
        jQuery(".massage-type-list").slideToggle();
        jQuery(this).toggleClass("active");
    });

    jQuery(document).click(function (event) {
        if (!jQuery(event.target).closest(".massage-type-list, .massage-type").length) {
            jQuery(".massage-type-list").slideUp();
            jQuery(".default-all-massage").removeClass("active");
        }
    });

    jQuery(".chat-items").click(function () {
        jQuery(".full-massage-card").addClass("active");
    });
    jQuery(".back-chatlist button").click(function () {
        jQuery(".full-massage-card").removeClass("active");
    });

    // video call page

    jQuery(".perticipent-show-hide").click(function () {
        jQuery(this).toggleClass("active");
        jQuery(".perticent-list").slideToggle();
    });
    jQuery(".switch-btn button").click(function () {
        jQuery(".switch-btn button").removeClass("active");
        jQuery(this).addClass("active");
    });

    jQuery(".chat-show-hide").click(function () {
        jQuery(this).toggleClass("active");
        jQuery(".call-chat-box").slideToggle();
    });

    // video call slider js

    $(".student-cm-slider").owlCarousel({
        loop: true,
        items: 1,
        margin: 0,
        nav: false,
        dots: false,
    });
    $(".student-cam-prev").on("click", function () {
        $(".student-cm-slider").owlCarousel("prev");
    });
    $(".student-cam-next").on("click", function () {
        $(".student-cm-slider").owlCarousel("next");
    });

    let previousVolume = 50;

    $(".volume-btn").click(function () {
        let slider = $(".volume-slider");
        let icon = $(this).find("i");

        if (slider.val() > 0) {
            previousVolume = slider.val();
            slider.val(0).addClass("muted");
            icon.removeClass("fa-volume-high").addClass("fa-volume-xmark");
        } else {
            slider.val(previousVolume).removeClass("muted");
            icon.removeClass("fa-volume-xmark").addClass("fa-volume-high");
        }
    });

   
});

$("#earn-chart").circleProgress({
    size: "188",
    borderSize: "20",
    progress: "75",
    initialProgress: "30",
    innerColor: "#D9D9D9",
    outerColor: "#20C997"
});

$("#earn-chart2").circleProgress({
    size: "188",
    borderSize: "20",
    progress: "45",
    initialProgress: "25",
    innerColor: "#D9D9D9",
    outerColor: "#8328BC"
});

$("#earn-chart3").circleProgress({
    size: "188",
    borderSize: "20",
    progress: "55",
    initialProgress: "25",
    innerColor: "#D9D9D9",
    outerColor: "#F5F85C"
});



 // find tutor page











