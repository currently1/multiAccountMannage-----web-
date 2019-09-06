
/*
footer {width:100%;visibility: 'hidden';}
+ 使用padding填充footer
+ 不要使用 html.body{height:100%;}；若使用需要修改代码	
*/
setStickyFooter($('.footer'));
/**
 * @param {jqueryDOM} $footer  footer的jqDom  默认：$('footer')
 * @param {jqueryDOM} $tabsArr 选项卡点击的jq对象 // 其他会影响到文档的高度情况自行添加 
 */
function setStickyFooter($footer, $tabsArr) { // loaded  MutationObserver resize  tabClick  loadMore Refresh
    var MutationObserver = (function () { // FF14+ ,Chrome26+ ,Opera15+ , IE11+, Safari6.1+
        var prefixes = ['WebKit', 'Moz', 'O', 'Ms', ''];
        for (var i = 0; i < prefixes.length; i++) {
            if (prefixes[i] + 'MutationObserver' in window) {
                return window[prefixes[i] + 'MutationObserver'];
            };
        };
        return false;
    }());
    // MutationObserver 相关
    var target = document.body;
    var observer;
    var config = {
        attributes: true,
        childList: true,
        characterData: true,
        subtree: true
    };

    if (MutationObserver) {
        observer = new MutationObserver(mutationObjectCallback); // callback  asyn
    };

    function mutationObjectCallback(mutationRecordsList) {
        stickyFooter();
    };

    function stickyFooter() {
        if (MutationObserver) {
            observer.disconnect();
        };
        var footerHeight = 0,
            footerTop = 0;
         $footer = $footer || $("footer");

        footerHeight = $footer.outerHeight();
        footerTop = ($(window).scrollTop() + $(window).height() - footerHeight) + "px";
        if (($(document.body).outerHeight()) < $(window).height()) {
            $footer.css({
                visibility: 'visible',
                position: "absolute",
                top: footerTop
            });
        } else {
            $footer.css({
                visibility: 'visible',
                position: "static"
            });
        };
        //reconnect
        if (MutationObserver) {
            observer.observe(target, config);
        };
    }
    // onload
    window.onload = function () {
        stickyFooter();
        if (MutationObserver) {
            observer.observe(target, config);
        } else {
            setInterval(stickyFooter, 500);
        };
    };
    // resize
    window.onresize = function () {
        stickyFooter();
    };
    // tabclick
    if (!!$tabsArr) {
        $tabsArr.click(stickyFooter);
    };
};
