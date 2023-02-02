from app import session
from flask_jwt_extended import *
from flask import render_template, redirect, jsonify, request, flash
from app.models.credential_model import credentials
from app.models.transaction_model import transaction
from app.controllers.all_controller import makeProxy, makeClient, send_mail
from sqlalchemy import func
import uuid
import polling
import datetime


def is_correct_response(resp):
    print(resp)
    return resp


def fetch_payment_details(merchant_id, api_key, api_secret):
    client = makeClient(api_key, api_secret, merchant_id)
    resp = client.Code.get_payment_details(merchant_id)
    if (resp['data'] == 'None'):
        return {
            'error': 'true'
        }
    return resp['data']['status']


def fetch_user_details(merchant_id, api_key, api_secret):
    client = makeClient(api_key, api_secret, merchant_id)
    resp = client.Code.get_payment_details(merchant_id)
    if (resp['data'] == 'None'):
        return {
            'error': 'true'
        }

    return resp['data']['orderItems'][0]['name']


def fetch_amount_details(merchant_id, api_key, api_secret):
    client = makeClient(api_key, api_secret, merchant_id)
    resp = client.Code.get_payment_details(merchant_id)
    if (resp['data'] == 'None'):
        return {
            'error': 'true'
        }
    return resp['data']['amount']['amount']


def paymentPaypay(amount, user):
    adminSetting = session.query(credentials).first()
    client = makeClient(adminSetting.PayPay_API_KEY,adminSetting.PayPay_API_SECRET, adminSetting.PayPay_MERCHANT_ID)
    merchantPaymentId = uuid.uuid4().hex
    print(client)

    if amount < adminSetting.min_input or amount > adminSetting.max_input:
        if amount < adminSetting.min_input:
            error = "Top up amount should be more than or equal with the Minimum Purchase (" + str(
                adminSetting.min_input) + ")"
        else:
            error = "Top up amount should be less than or equal with the Maximum Purchase (" + str(
                adminSetting.max_input) + ")"
        response = {
            'status': 'error',
            'message': error
        }
        return jsonify(response)
    proxy = makeProxy(adminSetting.Primary_Server_Address)
    auth = adminSetting.auth
    # proxy.api.getUserAccountBalance(auth,user)
    # print(proxy.api.getUserAccountBalance(auth,user))
    if proxy.api.isUserExists(auth, user):
        FRONTEND_PATH = adminSetting.Payment_Gateway_Address+"/check"
        qr = {
            "merchantPaymentId": merchantPaymentId,
            "codeType": "ORDER_QR",
            "redirectUrl": "{}/{}".format(FRONTEND_PATH, merchantPaymentId),
            "redirectType": "WEB_LINK",
            "orderDescription": "Papercutポイントの追加購入",
            "orderItems": [{
                "name": (user),
                "category": "Credit",
                "quantity": 1,
                "productId": "00001",
                "unitPrice": {
                    "amount": int(amount),
                    "currency": "JPY"
                }
            }],
            "amount": {
                "amount": int(amount),
                "currency": "JPY"
            },
        }

        response = client.Code.create_qr_code(qr)
        qrcode = (response['data']['url'])
        response = {
            'status': 'success',
            'paypaylink': qrcode,
            "merchantPaymentId": merchantPaymentId,
            "orderDescription": "Papercutポイントの追加購入",
            "orderItems": [{
                "name": (user),
                "category": "Credit",
                "quantity": 1,
                "productId": "00001",
                "unitPrice": {
                    "amount": int(amount),
                    "currency": "JPY"
                }
            }],
            "amount": {
                "amount": int(amount),
                "currency": "JPY"
            },
        }
        session.close()
        return jsonify(response)
    else:
        response = {
            'status': 'user not found',
            'message': 'User not exist in papercut',
        }
        session.close()
        return jsonify(response)


def paypayCheck(merch_id):
    adminSetting = session.query(credentials).first()
    redirect_url = adminSetting.Primary_Server_Address+'/app?service=page/UserSummary'
    client = makeClient(adminSetting.PayPay_API_KEY,
                        adminSetting.PayPay_API_SECRET, adminSetting.PayPay_MERCHANT_ID)
    multiplier = adminSetting.multiplier
    resp = client.Code.get_payment_details(merch_id)
    try:
        polling.poll(
            lambda: fetch_payment_details(
                merch_id) == 'COMPLETED' or fetch_payment_details(merch_id) == 'FAILED',
            check_success=is_correct_response,
            step=2,
            timeout=240)
        if (fetch_payment_details(merch_id, adminSetting.PayPay_API_KEY, adminSetting.PayPay_API_SECRET) == 'COMPLETED'):
            record = session.query(transaction).filter(
                transaction.MerchantPaymentID == merch_id).first()
            if record == None:
                user = fetch_user_details(
                    merch_id, adminSetting.PayPay_API_KEY, adminSetting.PayPay_API_SECRET)
                amount = float(fetch_amount_details(
                    merch_id, adminSetting.PayPay_API_KEY, adminSetting.PayPay_API_SECRET))
                credit = amount*multiplier
                proxy = makeProxy(adminSetting.Primary_Server_Address)
                auth = adminSetting.auth
                prev_balance = proxy.api.getUserAccountBalance(auth, user)
                proxy.api.adjustUserAccountBalance(
                    auth, user, credit, "PayPayによるポイント追加, 注文ID :"+str(merch_id))
                balance = proxy.api.getUserAccountBalance(auth, user)
                newTransaction = transaction(
                    Time=str(datetime.datetime.now()),
                    MerchantPaymentID=merch_id, Account=user,
                    Method='PayPay',
                    Amount=amount,
                    Point = credit
                )
                session.add(newTransaction)
                session.commit()
                curr_balance = proxy.api.getUserAccountBalance(auth, user)
                email = proxy.api.getUserProperty(auth, user, 'email')
                send_mail("Papercut Points Purchase Succeed", email, 'mail/payment_succeed.html',payment_id = merch_id, payment_method="PayPay",  multiplier=multiplier, amount=amount, prev_points=prev_balance, curr_points= curr_balance)
                body = render_template('success.html', balance=balance)
                session.close()
                return (body, 200, {("Refresh", "5; url={}".format(redirect_url))})
            else:
                body = ("ポイント追加をキャンセルします。5秒後PaperCut ユーザインタフェースへ移動します。")
                session.close()
                return (body, 200, {("Refresh", "5; url={}".format(redirect_url))})
        else:
            if redirect_url is None:
                session.close()
                return "Cancelled. Please close this tab/window and return to PaperCut"
            else:
                session.close()
                body = ("ポイント追加をキャンセルします。5秒後PaperCut ユーザインタフェースへ移動します。")
                return (body, 200, {("Refresh", "5; url={}".format(redirect_url))})
    except:
        body = ("ポイント追加をキャンセルします。5秒後PaperCut ユーザインタフェースへ移動します。")
        return (body, 200, {("Refresh", "5; url={}".format(redirect_url))})
