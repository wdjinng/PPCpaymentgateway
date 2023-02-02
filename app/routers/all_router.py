from flask import Flask, request, render_template, redirect, jsonify
import uuid
import datetime
import pymysql
from app import app, session, db
from app.controllers import all_controller, paypay_controller, paypal_controller
from app.controllers.all_controller import token_required, send_mail, makeProxy

from flask import request, Blueprint

allroute_blueprint = Blueprint("all_router", __name__)


# @app.errorhandler(404)
# def page_not_found(error):
#     return render_template('error.html', mssg="page not found"), 404


@app.route('/')
def wrongUrl():
    return("Please log into PaperCut and set top up your account from there")


@app.route('/admin/setting', methods=['GET'])
def adminSetting():
    return all_controller.getAdminSetting()


@app.route('/admin/setting/logo', methods=['GET'])
def companyLogo():
    return all_controller.getCompanyLogo()


@app.route('/user/list', methods=['GET'])
def userList():
    return all_controller.getUserList()


@app.route("/transaction/list/<string:user>", methods=["GET"])
def userTransactionList(user):
    return all_controller.getUserTransactionListDetailed(user)


@app.route('/transaction/list', methods=['GET'])
def transactionList():
    return all_controller.getTransactionList()


@app.route('/transaction/monthly', methods=['GET'])
def transactionMonthly():
    return all_controller.getTransactionMonthly()


@app.route('/admin/setting/update', methods=['PUT'])
def adminUpdate():
    req = request.form
    if 'company_logo' not in request.files:
        file = ''
    else:
        file = request.files['company_logo']
    return all_controller.updateAdminSetting(file, **req)


@app.route('/topup/', methods=['GET'])
def promptUser():
    user = request.args.get('user')
    lang = request.args.get('lang')
    return all_controller.generateToken(user, lang)


@app.route('/payment/')
@token_required
def verify():
    token = request.args.get('t')
    lang = request.args.get('lang')
    return all_controller.userTopUp(token, lang)


@app.route('/pagetopup/', methods=['GET'])
def promptPageUser():
    user = request.args.get('user')
    lang = request.args.get('lang')
    return all_controller.generatePageToken(user, lang)


@app.route('/paymentpage/')
@token_required
def verifyPage():
    token = request.args.get('t')
    lang = request.args.get('lang')
    return all_controller.userTopUpPage(token, lang)


@app.route('/paypay/', methods=['GET', 'POST'])
def paypay():
    req = request.json
    amount = req['amount']
    user = req['user']
    return paypay_controller.paymentPaypay(float(amount), user)


@app.route('/check/<merch_id>', methods=['GET', 'OPTIONS'])
def check(merch_id):
    return paypay_controller.paypayCheck(merch_id)


@app.route('/btclient', methods=['GET'])
def getBTClientToken():
    return paypal_controller.generate_client_token()


@app.route('/paypal/', methods=['GET', 'POST'])
def paypal():
    # req = request.json
    # amount = req['amount']
    # user = req['user']
    # nonce_from_the_client = req["payment_method_nonce"]
    amount = request.form["amount"]
    user = request.form["user"]
    method = request.form["method"]
    nonce_from_the_client = request.form["payment_method_nonce"]
    return paypal_controller.paymentPayPal(str(amount), user, method, nonce_from_the_client)


@app.route('/checkouts/<transaction_id>/<payment_method>', methods=['GET'])
def checkouts(transaction_id, payment_method):
    return paypal_controller.paypal_checkout(transaction_id, payment_method)


@app.route("/cancel/")
def cancel():
    #body =("ポイント追加をキャンセルします。5秒後PaperCut ユーザインタフェースへ移動します。")
    #body =("5秒後PaperCut ユーザインタフェースへ移動します。")
    redirect_url = all_controller.getRedirect()

    return render_template("cancel.html", mssg="5秒後PaperCut ユーザインタフェースへ移動します。"), 200, {("Refresh", "5; url={}".format(redirect_url))}


@app.route('/testmail/<transaction_id>', methods=['GET'])
def testemail(transaction_id):
    return paypal_controller.emailTest(transaction_id)


@app.route('/invoicedownload/<transaction_id>', methods=['GET'])
def invoiceDownload(transaction_id):
    return all_controller.generateInvoice(transaction_id)
