var host = window.location;
var socket = io.connect('http://127.0.0.1:5000');
var _strategy = new Object()
function sortTime(a, b) {
    return b.logTime.replace(/:/g, "") - a.logTime.replace(/:/g, "")
}
function sortVtOrderID(a, b) {
    return parseInt(b.match(/[0-9]*/g).join("")) - parseInt(a.match(/[0-9]*/g).join(""))
}
new Vue({
    el: '#app',
    data: function () {
        return {
            table_height: (window.innerHeight - 70) / 3 - 15 || 250,
            winHeight: window.innerHeight,
            topFrame: window.innerHeight * 2 / 3 - 65 + "px",
            bottomFrame: window.innerHeight / 3 - 65 + "px",
            leftTradeHeight: (window.innerHeight - 50) + 'px',
            selected_data: [],
            form: {
                volume: 1,
                vtSymbol: '',
                lastPrice: '',
                direction: '',
                offset: '',
                priceType: '',
            },
            loginForm: {
                user: "",
                pwd: ""
            },
            LoginFormVisible: true,
            loadingbool: false,
            formLabelWidth: '120px',
            eAccount: [],
            eTick: [],
            tickObj: {},
            eContract: [],
            connection: '未连接',
            activeTab: "home",
            activeTabLeft: 'trade',
            activeTabRight: 'position',
            log: [], //日志
            position: [], //持仓
            order: [], //委托
            orderObj: {}, //委托对象
            trade: [], //成交
            account: [], //资金
            error: [], //错误
            contract: [], //合约查询结果
            leftTrade: {}, //存放左侧交易区显示数据
            config: {}, //存放token等数据
            strategy: {}, //策略名
            ctaLog: [],
            loading: {
                subScribe: false,
                order: false,
                contract: false,
                strategy: false,
                // <!--<!--token: false,-->-->
            },
        }
    },
    created: function () {
        this.gAccount()
        this.gConnectionStatus()
        this.gTick()
        this.gLog()
        this.gPosition()
        this.gError()
        this.gOrder()
        this.gTrade()

    },
    methods: {

        // <!--onLogin() {-->
        //     <!--console.log(this.loginForm.user)-->
        //     <!--let userName = this.loginForm.user,-->
        //         <!--pwd = this.loginForm.pwd;-->
        //     <!--this.gToken(userName, pwd)-->
        // <!--},-->
        onLogin() {
            const that = this;
            axios.get(host)
                .then(function (res) {
                    that.loading.token = false;
                    //console.log(host)
                    //console.log(socket)
                    that.$message({ message: '已登录', type: 'success' });
                    that.LoginFormVisible = false

                    //that.onLoadInfo('account', 'account')
                    // that.onLoadInfo('trades', 'trade')
                    //that.onLoadInfo('position', 'position')
                    // that.onLoadInfo('order', 'order')
                    // that.onLoadInfo('log', 'log')
                    //  that.onLoadInfo('error', 'error')
                    //that.LoginFormVisible = false

                });
        },
        doAction(e, type) {
            // <!--if (this.config.token == undefined || this.config.token == "") {-->
            //     <!--this.$alert('请先登录', '警告', {confirmButtonText: '确定',});-->
            //     <!--return;-->
            // <!--}-->

            if (this.config.gateway == undefined || this.config.gateway == "") {
                this.$alert('请先连接CTP', '警告', { confirmButtonText: '确定', });
                return;
            }

            let name = e,
                that = this,
                info = "";
            switch (type) {
                case "init":
                    info = "初始化"
                    break;
                case "stop":
                    info = "停止"
                    break;
                case "start":
                    info = "启动"
                    break;
            }

            axios.post(host + "/ctastrategy/" + type, {
                name: name,
                // <!--token: this.config.token-->
            })
                .then(res => {
                    if (res.data.result_code == "success") {
                        that.$message({ message: name + info + '成功', type: 'success' });
                        if (type == "start") {
                            that.gCtaStrategy()
                        }
                    } else {
                        that.$message({ message: name + info + '成功', type: 'fail' });
                    }
                })
                .catch(res => {
                    that.$message({ message: name + info + '成功', type: 'fail' });
                })
        },
        doOnLoad() {

            // if (this.config.token == undefined || this.config.token == "") {
            //     this.$alert('请先登录', '警告', {confirmButtonText: '确定',});
            //     return;
            // }

            if (this.config.gateway == undefined || this.config.gateway == "") {
                this.$alert('请先连接CTP', '警告', { confirmButtonText: '确定', });
                return;
            }


            const that = this;
            let strategy = {};
            that.loading.strategy = true;
            axios.post(host + '/ctastrategy/load', {
                //token: this.config.token
            })
                .then(res => {
                    if (res.data.result_code !== "success") {
                        that.$notify({ title: '警告', message: 'ctastrategy/load接口报错', type: 'warning', duration: 0, });
                        return;
                    } else {
                        let strategy = res.data.data;
                        strategy.forEach((item) => {
                            _strategy[item] = { name: item };
                            that.gParams(item)
                            that.gVar(item)
                        })
                    }
                })
        },
        gVar(name) {

            // if (this.config.token == undefined || this.config.token == "") {
            //     this.$alert('请先登录', '警告', {confirmButtonText: '确定',});
            //     return;
            // }

            if (this.config.gateway == undefined || this.config.gateway == "") {
                this.$alert('请先连接CTP', '警告', { confirmButtonText: '确定', });
                return;
            }

            const that = this,
                _var = new Object();
            axios.get(host + "/ctastrategy/var?name=" + name)
                .then(res => {
                    if (res.data.result_code !== "success") {
                        that.$notify({ title: '警告', message: 'ctastrategy/var接口报错', type: 'warning', duration: 0, });
                        return;
                    } else {
                        _strategy[name]['var'] = res.data.data;
                        that.strategy = _strategy;
                        that.loading.strategy = false;
                    }
                })
                .catch(res => {
                    that.$notify({ title: '警告', message: 'ctastrategy/var接口报错', type: 'warning', duration: 0, });
                })
        },

        gCtaStrategy() {
            let that = this;

            socket.on("eCtaStrategy.", function (data) {
                let name = data.name;
                delete data['name'];
                that.strategy[name]['var'] = data;
            });
        },

        gCtaLog() {
            let that = this,
                logObj = new Object();

            socket.on("eCtaLog", function (data) {
                logObj[data.logTime] = data
                let dataArr = that.ctaLog.concat(Object.values(logObj));
                dataArr.sort(sortTime)
                that.ctaLog = dataArr;
            });
        },

        gParams(name) {

            // if (this.config.token == undefined || this.config.token == "") {
            //     this.$alert('请先登录', '警告', {confirmButtonText: '确定',});
            //     return;
            // }

            if (this.config.gateway == undefined || this.config.gateway == "") {
                this.$alert('请先连接CTP', '警告', { confirmButtonText: '确定', });
                return;
            }

            const that = this;
            axios.get(host + "/ctastrategy/param?name=" + name)
                .then(res => {
                    if (res.data.result_code !== "success") {
                        that.$notify({ title: '警告', message: 'ctastrategy/param接口报错', type: 'warning', duration: 0, });
                        return;
                    } else {
                        _strategy[name]['par'] = res.data.data;
                        that.strategy = _strategy;
                        that.loading.strategy = false;
                    }

                })
                .catch(res => {
                    that.$notify({ title: '警告', message: 'ctastrategy/param接口报错', type: 'warning', duration: 0, });
                })
        },

        onLoadInfo(apiName, dataArr) {
            const that = this;


            gInfo(apiName)
            //} else {
            //    axios.get(host + '/token?username=test&password=test', {

            //          })
            //        .then(function(res) {
            //            if (res.status == 200 && res.data.result_code == "success") {
            //               let token = res.data.data
            //                gInfo(apiName, token)
            //             } else {
            //               that.$notify({ title: '警告', message: 'token获取失败', type: 'warning', duration: 0, });
            //            }
            //        })
            //       .catch(function(res) {
            //            that.$notify({ title: '警告', message: 'token获取失败', type: 'warning', duration: 0, });
            //        });
            //  }

            function gInfo(apiName) {
                axios.get(host + "/" + apiName)
                    .then(res => {
                        if (res.data.result_code == "success") {
                            //console.log(res.data.data)
                            if (apiName == "order") {
                                res.data.data.forEach((item) => {
                                    item["_vtOrderID"] = item.vtOrderID.replace(/\./g, "")
                                    that.orderObj[item._vtOrderID] = item;
                                })
                                sorted_order_list = Object.keys(that.orderObj).sort(sortVtOrderID);
                                for (i in sorted_order_list) {
                                    that.order.push(that.orderObj[sorted_order_list[i]]);
                                }
                            }
                            else {
                                that[dataArr] = that[dataArr].concat(res.data.data).reverse()
                            }

                        } else {
                            that.$notify({ title: '警告', message: '服务异常，获取信息失败1', type: 'warning', duration: 3000, });
                        }
                    })
                    .catch(res => {
                        that.$notify({ title: '警告', message: '服务异常，获取信息失败2', type: 'warning', duration: 3000, });
                    })
            }
        },
        onSubmit(e) {

            // if (this.config.token == undefined || this.config.token == "") {
            //     this.$alert('请先登录', '警告', {confirmButtonText: '确定',});
            //     return;
            // }

            if (this.config.gateway == undefined || this.config.gateway == "") {
                this.$alert('请先连接CTP', '警告', { confirmButtonText: '确定', });
                return;
            }

            if (this.form.vtSymbol == "") {
                this.$alert('请填写代码！', '警告', { confirmButtonText: '确定', });
                return;
            }
            if (this.form.lastPrice == "") {
                this.$alert('请填写价格！', '警告', { confirmButtonText: '确定', });
                return;
            }
            if (this.form.volume == "") {
                this.$alert('请填写数量！', '警告', { confirmButtonText: '确定', });
                return;
            }
            if (this.form.priceType == "") {
                this.$alert('请选择价格类型！', '警告', { confirmButtonText: '确定', });
                return;
            }
            if (this.form.direction == "") {
                this.$alert('请选择方向类型！', '警告', { confirmButtonText: '确定', });
                return;
            }
            if (this.form.offset == "") {
                this.$alert('请选择开平！', '警告', { confirmButtonText: '确定', });
                return;
            }

            this.loading.order = true;

            const that = this;
            axios.post(host + '/order', {
                vtSymbol: this.form.vtSymbol,
                price: this.form.lastPrice,
                volume: this.form.volume,
                priceType: this.form.priceType,
                direction: this.form.direction,
                offset: this.form.offset,
                //token: this.config.token,
            })
                .then(function (res) {
                    that.loading.order = false;
                    if (res.data.result_code == "success") {
                        that.$message({ message: '发单成功', type: 'success' });
                    } else {
                        that.$notify({ title: '警告', message: '服务异常，发单失败', type: 'warning', duration: 3000, });
                    }
                })
                .catch(function (err) {
                    that.loading.order = false;
                    that.$notify({ title: '警告', message: '服务异常，发单失败', type: 'warning', duration: 3000, });
                });
        },
        onSubscribe(target) {

            // if (this.config.token == undefined || this.config.token == "") {
            //     this.$alert('请先登录', '警告', {confirmButtonText: '确定',});
            //     return;
            // }

            if (this.config.gateway == undefined || this.config.gateway == "") {
                this.$alert('请先连接CTP', '警告', { confirmButtonText: '确定', });
                return;
            }

            const that = this;

            if (typeof (target) !== "object") {
                var _vtSymbol = target
            } else {
                var _vtSymbol = this.form.vtSymbol
            }

            //if (this.config.token == undefined || this.config.token == "") {
            //   this.gToken()
            // }

            if (_vtSymbol == undefined || _vtSymbol == "") {
                return this.$alert('请输入代码', '提示', {
                    confirmButtonText: '确定',
                });
            } else {
                this.loading.subScribe = true;
                axios.post(host + "/tick", {
                    vtSymbol: _vtSymbol,
                    //token: this.config.token
                })
                    .then(res => {
                        that.loading.subScribe = false;
                        if (res.data.result_code == "success") {
                            let target = _vtSymbol
                            that.clickTick(target)
                            that.form.vtSymbol = target;
                            that.$message({ message: '订阅成功', type: 'success' });
                        } else {
                            that.$notify({ title: '警告', message: '订阅失败', type: 'warning', duration: 3000, });
                        }
                    })
                    .catch(res => {
                        that.loading.subScribe = false;
                        that.$notify({ title: '警告', message: '服务异常，订阅失败', type: 'warning', duration: 3000, });
                    })
            }
        },
        dOrder(e) {

            // if (this.config.token == undefined || this.config.token == "") {
            //     this.$alert('请先登录', '警告', {confirmButtonText: '确定',});
            //     return;
            // }

            if (this.config.gateway == undefined || this.config.gateway == "") {
                this.$alert('请先连接CTP', '警告', { confirmButtonText: '确定', });
                return;
            }
            console.log(e.vtOrderID);
            let vtOrderID = e.vtOrderID,
                that = this;
            axios.delete(host + "/order?vtOrderID=" + vtOrderID)
                .then(res => {
                    if (res.data.result_code == "success") {
                        that.$message({ message: '撤单已提交', type: 'success' });
                    } else {
                        that.$notify({ title: '警告', message: '服务异常，撤单提交失败', type: 'warning', duration: 2000, });
                    }
                })
                .catch(res => {
                    that.$notify({ title: '警告', message: '服务异常，撤单提交失败', type: 'warning', duration: 2000, });
                })
        },
        dAllOrder(e) {

            // if (this.config.token == undefined || this.config.token == "") {
            //     this.$alert('请先登录', '警告', {confirmButtonText: '确定',});
            //     return;
            // }

            if (this.config.gateway == undefined || this.config.gateway == "") {
                this.$alert('请先连接CTP', '警告', { confirmButtonText: '确定', });
                return;
            }
            console.log(e.vtOrderID);
            let vtOrderID = "",
                that = this;
            axios.delete(host + "/order?vtOrderID=" + vtOrderID)
                .then(res => {
                    if (res.data.result_code == "success") {
                        that.$message({ message: '撤单已提交', type: 'success' });
                    } else {
                        that.$notify({ title: '警告', message: '服务异常，撤单提交失败', type: 'warning', duration: 2000, });
                    }
                })
                .catch(res => {
                    that.$notify({ title: '警告', message: '服务异常，撤单提交失败', type: 'warning', duration: 2000, });
                })
        },
        handleClick(row) {
            this.onSubscribe(row.vtSymbol)
        },
        handleTab(tab) {
            const that = this;
            that.loading.contract = true;
            if (tab.name == "search") {
                this.gContract()
            } else if (tab.name == "cta") {
                this.judgeIfStrategy()
                this.gCtaLog()
            }
        },
        judgeIfStrategy() {

            // if (this.config.token == undefined || this.config.token == "") {
            //     this.$alert('请先登录', '警告', {confirmButtonText: '确定',});
            //     return;
            // }

            if (this.config.gateway == undefined || this.config.gateway == "") {
                this.$alert('请先连接CTP', '警告', { confirmButtonText: '确定', });
                return;
            }

            let that = this;
            axios.get(host + "/ctastrategy/name")
                .then(res => {
                    let nameArray = res.data.data;
                    nameArray.forEach(function (item) {
                        _strategy[item] = { name: item };
                        that.gParams(item)
                        that.gVar(item)
                    })
                })
                .catch(res => {
                    that.$notify({ title: '警告', message: '连接异常', type: 'warning', duration: 4500, });
                })
        },
        gContract() {

            // if (this.config.token == undefined || this.config.token == "") {
            //     this.loading.contract = false;
            //     this.$alert('请先登录', '警告', {confirmButtonText: '确定',});
            //     return;
            // }

            if (this.config.gateway == undefined || this.config.gateway == "") {
                this.loading.contract = false;
                this.$alert('请先连接CTP', '警告', { confirmButtonText: '确定', });
                return;
            }

            const that = this;
            if (that.contract.length == 0) {
                axios.get(host + "/contract")
                    .then(res => {
                        that.loading.contract = false;
                        if (res.data.result_code == "success") {
                            that.contract = res.data.data
                        } else {
                            that.$notify({ title: '警告', message: '连接异常', type: 'warning', duration: 4500, });
                        }
                    })
                    .catch(res => {
                        that.$notify({ title: '警告', message: '连接异常', type: 'warning', duration: 4500, });
                    })
            }
        },
        gGateway() {
            const that = this;
            ss = host + '/gateway';

            axios.post(host + '/gateway', {
                //token: this.config.token,
                gatewayName: 'CTP'

            })
                .then(function (res) {
                    that.config.gateway = true;
                    that.$message({ message: '已连接CTP', type: 'success' });
                    if (that.loadingbool == false) {
                        that.onLoadInfo('account', 'account')
                        that.onLoadInfo('trades', 'trade')
                        that.onLoadInfo('position', 'position')
                        that.onLoadInfo('order', 'order')
                        that.onLoadInfo('log', 'log')
                        that.onLoadInfo('error', 'error')
                        that.loadingbool = true
                    }
                })
                .catch(function (err) {
                    console.log("res", err)
                });
        },
        gTick(target) {
            let that = this,
                tick = new Object(),
                tickObj = new Object();
            socket.on("eTick.", function (data) {
                console.log(socket)
                tick[data.vtSymbol] = data
                that.tickObj = tick
                that.eTick = Object.values(tick).reverse()
            });
        },
        clickTick(e) {
            let that = this,
                tick = new Object(),
                tickObj = new Object(),
                target = e.vtSymbol || e;
            if (that.tickObj[target] !== undefined) {
                that.form.lastPrice = that.tickObj[target].lastPrice
            }
            that.form.vtSymbol = target
            socket.on("eTick.", function (data) {
                that.leftTrade = that.tickObj[target]
                that.leftTrade.priceRatio = (((that.tickObj[target].lastPrice / that.tickObj[target].preClosePrice) - 1) * 100.0).toFixed(2) + "%"
                // if (that.tickObj[target] !== undefined) {
                //     if (that.tickObj[target].lastPrice == undefined) {
                //         that.form.lastPrice = that.tickObj[target].lastPrice
                //     }
                // }
            });
        },
        gOrder() {
            let that = this,
                orderObj = new Object();
            socket.on("eOrder.", function (data) {
                console.log(data);
                data["_vtOrderID"] = data.vtOrderID.replace(/\./g, "")
                that.orderObj[data._vtOrderID] = data;
                sorted_order_list = Object.keys(that.orderObj).sort(sortVtOrderID);
                console.log(sorted_order_list);
                order_tmp = []
                for (i in sorted_order_list) {
                    order_tmp.push(that.orderObj[sorted_order_list[i]]);
                }
                that.order = order_tmp
                console.log(that.order)
            });
        },
        gAccount() {
            let that = this,
                accounts = new Object();
            socket.on("eAccount.", function (data) {
                console.log(data)
                accounts[data.vtAccountID] = data
                that.account = Object.values(accounts).reverse()
            });
        },
        gPosition() {
            let that = this,
                positions = new Object();
            socket.on("ePosition.", function (data) {
                console.log(data)
                positions[data.vtPositionName] = data
                that.position = Object.values(positions).reverse()
            });
        },
        gTrade() {
            let that = this,
                trades = new Object();
            socket.on("eTrade.", function (data) {
                trades[data.vtOrderID] = data
                that.trade = that.trade.concat(Object.values(trades)).reverse()
            });
        },
        gError() {
            let that = this,
                errObj = new Object();
            socket.on("eError.", function (data) {
                errObj[data.errorTime] = data
                that.error = that.error.concat(Object.values(errObj)).reverse()
                // that.error = Object.values(errObj).reverse()
            });
        },
        gLog() {
            let that = this,
                logObj = new Object();
            socket.on("eLog", function (data) {
                logObj[data.logTime] = data
                that.log = that.log.concat(Object.values(logObj)).reverse()
            });
        },
        handleTabLeft(tab, event) { },
        handleTabRight(tab, event) { },
        gConnectionStatus() {
            const that = this;
            socket.on('disconnect', function () {
                that.connection = '已断开'
                that.$notify({
                    title: '警告',
                    message: '服务器连接已断开',
                    type: 'warning',
                    duration: 4500,
                });
            });
            socket.on('connect_failed', function () {
                that.connection = '连接失败'
                that.$notify({
                    title: '警告',
                    message: '服务器连接失败',
                    type: 'warning',
                    duration: 4500,
                });
            });
            socket.on('connect', function () {
                that.connection = '已连接'
                that.$notify({
                    title: '成功',
                    message: '服务器连接成功',
                    type: 'success',
                    duration: 2000,
                });
            });
            socket.on('connecting', function () {
                that.connection = '正在连接'
            });
            socket.on('error', function () {
                that.connection = '连接错误'
                that.$notify({
                    title: '警告',
                    message: '服务器连接错误',
                    type: 'warning',
                    duration: 4500,
                });
            });
        },
    }
})