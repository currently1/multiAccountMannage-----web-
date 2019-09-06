$(function () {
    // 鐧诲綍椤�
    $('.login-main-bit i').on('click', function(){
        console.log(2);
        $('.login-main-bit input').val('');
    });

    // 閫氱敤渚ц竟鏍�
    $('.page-sidebar-list h6').each(function (index) { 
        var that = $(this);
        var addname = 'page-sidebar-' + index;
        that.parent().addClass(addname);
        if(that.siblings().size() !== 0){
            that.parent().addClass('page-sidebar-special');
        }
    });

    $('.page-sidebar-special h6 a').on('click', function(){
        var that = $(this).parents('li');
        that.addClass('cur').siblings().removeClass('cur');
    });

    // 鏌ヨ�缁撴灉
    $('.query-results-menu dt').on('click', function(){
        $(this).parent().addClass('cur').siblings().removeClass('cur');
    });

    // 绋嬪簭鍖栦氦鏄�
    $('.programmed-trading-left').on('click', function(){
        var that = $(this).find('.commoncaret-ascending');
        if(that.hasClass('cur')){
            that.removeClass('cur').siblings().addClass('cur');
        }else{
            that.addClass('cur').siblings().removeClass('cur');
        }
    });

    // 鑷�姩浜ゆ槗
    $('.manual-trading-title i').on('click', function(){
        var that = $(this);
        var num = $('.manual-trading-title input').val();
        if(that.hasClass('manual-trading-add')){
            num = num * 1 + 1;
        }else if(that.hasClass('manual-trading-subtract')){
            num = num * 1 - 1;
        }
        return $('.manual-trading-title input').val(num);
    });

    $('.manual-trading-table th').on('click', function(){
        var that = $(this).find('.commoncaret-ascending');
        if(that.hasClass('cur')){
            that.removeClass('cur').siblings().addClass('cur');
        }else{
            that.addClass('cur').siblings().removeClass('cur')
                .parents('th').siblings().find('.cur').removeClass('cur');
        }
    });

    $('.manual-trading-switch button').on('click', function(){
        var that = $(this);
        var index = that.index();
        that.addClass('cur').siblings().removeClass('cur')
            .parent().next().find('.manual-trading-bottom').eq(index).addClass('cur')
            .siblings().removeClass('cur');
    });

    // 涓�汉涓婚〉
    $('.personal-homepage-form button').on('click', function(){
        var that = $(this);
        if(that.hasClass('cur')){
            that.parent().submit();
        }else{
            that.addClass('cur').html('淇濆瓨').prev().attr('disabled', false).focus();
        }
    });

    $('.personal-homepage-form input').on('blur', function(){
        $(this).attr('disabled', true).next().removeClass('cur').html('鏇存敼')
    });

    $('.personal-homepage-edit').on('click', function(){
        $('.personal-homepage-mask').show();
    });

    //$('.personal-homepage-remove').click(function(){
        //$(this).parents('li').remove();
    //});

    $('.personal-homepage-mask input[type=button]').on('click', function(){
        $('.personal-homepage-mask').hide();
    });

    // 閫氱敤鍒嗛〉鍣�
    if(typeof layui != 'undefined') {
        var laypage = layui.laypage;
        laypage.render({
            elem: 'laypage',
            count: 100,
            layout: ['prev', 'page', 'next', 'limit', 'skip'],
            groups: 3,
            jump: function(obj){
            }
        });
    }
});