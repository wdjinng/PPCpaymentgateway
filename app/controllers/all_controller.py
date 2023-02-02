import mimetypes
from app import session, key, app, mail
import xmlrpc.client
import paypayopa
import jwt
from flask_jwt_extended import *
from flask import render_template, redirect, jsonify, request, make_response, send_from_directory
from app.models.credential_model import credentials
from app.models.transaction_model import transaction
from sqlalchemy import func, desc, asc
import uuid
import polling
import datetime
from functools import wraps
import os
from werkzeug.utils import secure_filename
from threading import Thread

from flask_mail import Message
import pdfkit


def makeClient(api_key, api_secret, merchant_id):
    client = paypayopa.Client(
        auth=(api_key, api_secret), production_mode=False)
    client.set_assume_merchant(merchant_id)
    return client


def makeProxy(papercutserver):
    host = papercutserver+"/rpc/api/xmlrpc"
    proxy = xmlrpc.client.ServerProxy(host)
    return proxy

# ==================function to send email asynchronusly


def async_send_mail(app, msg):
    with app.app_context():
        mail.send(msg)


def send_mail(subject, recipient, template, **kwargs):
    msg = Message(
        subject, sender=app.config['MAIL_DEFAULT_SENDER'], recipients=[recipient])
    msg.html = render_template(template, **kwargs)
    thr = Thread(target=async_send_mail, args=[app, msg])
    thr.start()
    return thr


def generateInvoice(transaction_id):
    trans = session.query(transaction).filter(
        transaction.MerchantPaymentID == transaction_id).first()
    adminSetting = session.query(credentials).first()
    proxy = makeProxy(adminSetting.Primary_Server_Address)
    auth = adminSetting.auth
    email = proxy.api.getUserProperty(auth, trans.Account, 'email')
    fullname = proxy.api.getUserProperty(auth, trans.Account, 'full-name')
    company_detail = {
        "logo": "http://127.0.0.1:5000/admin/setting/logo",
        "name": adminSetting.company_name,
        "email": adminSetting.company_email
    }
    user_detail = {
        "username": trans.Account,
        "fullname": fullname,
        "email": email
    }
    transaction_detail = {
        "id": transaction_id,
        "time": trans.Time,
        "method": trans.Method,
        "amount": trans.Amount,
        "points": trans.Point,
        "conversion": trans.Point/trans.Amount,
    }

    # config = pdfkit.configuration(
    #     wkhtmltopdf='E:\\programs\\wkhtmltopdf\\bin\\wkhtmltopdf.exe')
    config = pdfkit.configuration(
        wkhtmltopdf='C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe')
    html = render_template("receipt.html", company=company_detail,
                           user=user_detail, transaction=transaction_detail)
    pdf = pdfkit.from_string(html, False, configuration=config)

    response = make_response(pdf)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "inline; filename=Papercut Points Invoice.pdf"
    return response


# ==================controller for admin setting

def getAdminSetting():
    adminSetting = session.query(credentials).first()
    response = {
        'id': adminSetting.id,
        'PayPay_API_KEY': adminSetting.PayPay_API_KEY,
        'PayPay_API_SECRET': adminSetting.PayPay_API_SECRET,
        'PayPay_MERCHANT_ID': adminSetting.PayPay_MERCHANT_ID,
        'BT_ENVIRONMENT': adminSetting.BT_ENVIRONMENT,
        'BT_MERCHANT_ID': adminSetting.BT_MERCHANT_ID,
        'BT_PUBLIC_KEY': adminSetting.BT_PUBLIC_KEY,
        'BT_PRIVATE_KEY': adminSetting.BT_PRIVATE_KEY,
        'BT_APP_SECRET_KEY': adminSetting.BT_APP_SECRET_KEY,
        "company_name": adminSetting.company_name,
        "company_email": adminSetting.company_email,
        "company_logo": adminSetting.company_logo,
        'multiplier': adminSetting.multiplier,
        'min_input': adminSetting.min_input,
        'max_input': adminSetting.max_input,
        'auth': adminSetting.auth,
        'primary_server': adminSetting.Primary_Server_Address,
        'mssg1': adminSetting.mssg,
        'mssg2': adminSetting.mssg2,
        'mssg_JP': adminSetting.mssg_JP,
        'mssg2_JP': adminSetting.mssg2_JP,
        'main_message': adminSetting.main_message,
        'colour': adminSetting.colour,
    }
    session.close()
    return jsonify(response)


def getCompanyLogo():
    adminSetting = session.query(credentials).first()
    companyLogo = adminSetting.logo_file
    company_logo = adminSetting.company_logo
    filename = os.path.join(app.config['UPLOAD_FOLDER'], company_logo)
    print(filename)
    session.close()
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER']), company_logo)
    # return send_file(io.BytesIO(companyLogo),mimetype='image')


def getTransactionList():
    # transactions = session.query(transaction).all()
    transactions = session.query(transaction).order_by(desc(transaction.Time))
    all_transaction = []
    for items in transactions:
        trans = {
            'id': items.id,
            'time': items.Time,
            'merchantPaymentID': items.MerchantPaymentID,
            'account': items.Account,
            'method': items.Method,
            'amount': items.Amount,
            'point': items.Point,
        }
        all_transaction.append(trans)
    response = {
        'transactions': all_transaction,
    }
    session.close()
    return jsonify(response)


def getTransactionMonthly():
    # transactions = session.query(transaction).all()
    transactions = session.query(transaction.id, func.month(transaction.Time).label(
        'month'), func.sum(transaction.Amount).label(
        'totalAmount'), func.sum(transaction.Point).label(
        'totalPoint')).group_by(func.month(transaction.Time))
    months = []
    totalAmounts = []
    totalPoints = []
    for items in transactions:
        datetime_object = datetime.datetime.strptime(str(items.month), "%m")
        full_month_name = datetime_object.strftime("%B")
        months.append(full_month_name)
        totalAmounts.append(items.totalAmount)
        totalPoints.append(items.totalPoint)
    response = {
        'months': months,
        'totalAmounts': totalAmounts,
        'totalPoints': totalPoints,
    }
    session.close()
    return jsonify(response)


def getUserList():
    adminSetting = session.query(credentials).first()
    proxy = makeProxy(adminSetting.Primary_Server_Address)
    transactions = session.query(transaction.id, transaction.Account, func.sum(transaction.Amount).label(
        'totalAmount')).group_by(transaction.Account).order_by(asc(transaction.Time))
    allUser = []
    for items in transactions:
        trans = {
            'id': items.id,
            'account': items.Account,
            'totalAmount': items.totalAmount,
            'email': proxy.api.getUserProperty(adminSetting.auth, items.Account, 'email'),
            'balance': proxy.api.getUserProperty(adminSetting.auth, items.Account, 'balance'),
            'pagesPrinted': proxy.api.getUserProperty(adminSetting.auth, items.Account, 'print-stats.page-count'),
        }
        allUser.append(trans)
    print(transactions)
    response = {
        'users': allUser,
    }
    session.close()
    return jsonify(response)


def getUserTransactionListDetailed(user):
    transactions = session.query(transaction.id, func.max(transaction.Time).label('lastTime'), transaction.Method, func.sum(
        transaction.Amount).label('totalAmount')).filter(transaction.Account == user).group_by(transaction.Method)
    allTransaction = []
    for items in transactions:
        trans = {
            'id': items.id,
            'method': items.Method,
            'lastTime': items.lastTime,
            'totalAmount': items.totalAmount,
        }
        allTransaction.append(trans)
    print(transactions)
    response = {
        'transaction': allTransaction,
    }
    session.close()
    return jsonify(response)


ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg'])


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def updateAdminSetting(file, **request):
    # try:
    adminSetting = session.query(credentials).first()

    if request['PayPay_API_KEY'] != '':
        if isinstance(request['PayPay_API_KEY'], list):
            if len(request['PayPay_API_KEY']) == 0:
                PayPayAPI_KEY = adminSetting.PayPay_API_KEY
            else:
                PayPayAPI_KEY = request['PayPay_API_KEY'][0]
        else:
            PayPayAPI_KEY = request['PayPay_API_KEY']
    else:
        PayPayAPI_KEY = adminSetting.PayPay_API_KEY

    if request['PayPay_API_SECRET'] != '':
        if isinstance(request['PayPay_API_SECRET'], list):
            if len(request['PayPay_API_SECRET']) == 0:
                PayPayAPI_SECRET = adminSetting.PayPay_API_SECRET
            else:
                PayPayAPI_SECRET = request['PayPay_API_SECRET'][0]
        else:
            PayPayAPI_SECRET = request['PayPay_API_SECRET']
    else:
        PayPayAPI_SECRET = adminSetting.PayPay_API_SECRET

    if request['PayPay_MERCHANT_ID'] != '':
        if isinstance(request['PayPay_MERCHANT_ID'], list):
            if len(request['PayPay_MERCHANT_ID']) == 0:
                PayPayMERCHANT_ID = adminSetting.PayPay_MERCHANT_ID
            else:
                PayPayMERCHANT_ID = request['PayPay_MERCHANT_ID'][0]
        else:
            PayPayMERCHANT_ID = request['PayPay_MERCHANT_ID']
    else:
        PayPayMERCHANT_ID = adminSetting.PayPay_MERCHANT_ID

    if request['BT_ENVIRONMENT'] != '':
        if isinstance(request['BT_ENVIRONMENT'], list):
            if len(request['BT_ENVIRONMENT']) == 0:
                BT_ENVIRONMENT = adminSetting.BT_ENVIRONMENT
            else:
                BT_ENVIRONMENT = request['BT_ENVIRONMENT'][0]
        else:
            BT_ENVIRONMENT = request['BT_ENVIRONMENT']
    else:
        BT_ENVIRONMENT = adminSetting.BT_ENVIRONMENT

    if request['BT_MERCHANT_ID'] != '':
        if isinstance(request['BT_MERCHANT_ID'], list):
            if len(request['BT_MERCHANT_ID']) == 0:
                BT_MERCHANT_ID = adminSetting.BT_MERCHANT_ID
            else:
                BT_MERCHANT_ID = request['BT_MERCHANT_ID'][0]
        else:
            BT_MERCHANT_ID = request['BT_MERCHANT_ID']
    else:
        BT_MERCHANT_ID = adminSetting.BT_MERCHANT_ID

    if request['BT_PUBLIC_KEY'] != '':
        if isinstance(request['BT_PUBLIC_KEY'], list):
            if len(request['BT_PUBLIC_KEY']) == 0:
                BT_PUBLIC_KEY = adminSetting.BT_PUBLIC_KEY
            else:
                BT_PUBLIC_KEY = request['BT_PUBLIC_KEY'][0]
        else:
            BT_PUBLIC_KEY = request['BT_PUBLIC_KEY']
    else:
        BT_PUBLIC_KEY = adminSetting.BT_PUBLIC_KEY

    if request['BT_PRIVATE_KEY'] != '':
        if isinstance(request['BT_PRIVATE_KEY'], list):
            if len(request['BT_PRIVATE_KEY']) == 0:
                BT_PRIVATE_KEY = adminSetting.BT_PRIVATE_KEY
            else:
                BT_PRIVATE_KEY = request['BT_PRIVATE_KEY'][0]
        else:
            BT_PRIVATE_KEY = request['BT_PRIVATE_KEY']
    else:
        BT_PRIVATE_KEY = adminSetting.BT_PRIVATE_KEY

    if request['BT_APP_SECRET_KEY'] != '':
        if isinstance(request['BT_APP_SECRET_KEY'], list):
            if len(request['BT_APP_SECRET_KEY']) == 0:
                BT_APP_SECRET_KEY = adminSetting.BT_APP_SECRET_KEY
            else:
                BT_APP_SECRET_KEY = request['BT_APP_SECRET_KEY'][0]
        else:
            BT_APP_SECRET_KEY = request['BT_APP_SECRET_KEY']
    else:
        BT_APP_SECRET_KEY = adminSetting.BT_APP_SECRET_KEY

    if request['auth'] != '':
        if isinstance(request['auth'], list):
            if len(request['auth']) == 0:
                auths = adminSetting.auth
            else:
                auths = request['auth'][0]
        else:
            auths = request['auth']
    else:
        auths = adminSetting.auth

    if request['company_name'] != '':
        if isinstance(request['company_name'], list):
            if len(request['company_name']) == 0:
                companyName = adminSetting.company_name
            else:
                companyName = request['company_name'][0]
        else:
            companyName = request['company_name']
    else:
        companyName = adminSetting.company_name

    if request['company_email'] != '':
        if isinstance(request['company_email'], list):
            if len(request['company_email']) == 0:
                companyEmail = adminSetting.company_email
            else:
                companyEmail = request['company_email'][0]
        else:
            companyEmail = request['company_email']
    else:
        companyEmail = adminSetting.company_email

    if file == '':
        companyLogo = adminSetting.company_logo
    elif file != '' and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        companyLogo = filename
        if os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], adminSetting.company_logo)):
            os.remove(os.path.join(
                app.config['UPLOAD_FOLDER'], adminSetting.company_logo))
            print("The file has been deleted successfully")
        else:
            print("The file does not exist!")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    if request['multiplier'] != '':
        if isinstance(request['multiplier'], list):
            if len(request['multiplier']) == 0:
                multipliers = adminSetting.multiplier
            else:
                multipliers = request['multiplier'][0]
        else:
            multipliers = request['multiplier']
    else:
        multipliers = adminSetting.multiplier

    if request['min_input'] != '':
        if isinstance(request['min_input'], list):
            if len(request['min_input']) == 0:
                min_input = adminSetting.min_input
            else:
                min_input = request['min_input'][0]
        else:
            min_input = request['min_input']
    else:
        min_input = adminSetting.min_input

    if request['max_input'] != '':
        if isinstance(request['max_input'], list):
            if len(request['max_input']) == 0:
                max_input = adminSetting.max_input
            else:
                max_input = request['max_input'][0]
        else:
            max_input = request['max_input']
    else:
        max_input = adminSetting.max_input

    if request['primary_server'] != '':
        if isinstance(request['primary_server'], list):
            if len(request['primary_server']) == 0:
                primary_server = adminSetting.Primary_Server_Address
            else:
                primary_server = request['primary_server'][0]
        else:
            primary_server = request['primary_server']
    else:
        primary_server = adminSetting.Primary_Server_Address

    if request['main_message'] != '':
        if isinstance(request['main_message'], list):
            if len(request['main_message']) == 0:
                main_message = adminSetting.main_message
            else:
                main_message = request['main_message'][0]
        else:
            main_message = request['main_message']
    else:
        main_message = adminSetting.main_message

    if request['colour'] != '':
        if isinstance(request['colour'], list):
            if len(request['colour']) == 0:
                colour = adminSetting.colour
            else:
                colour = request['colour'][0]
        else:
            colour = request['colour']
    else:
        colour = adminSetting.colour

    session.query(credentials).filter(credentials.id == 1).update({
        "PayPay_API_KEY": PayPayAPI_KEY,
        "PayPay_API_SECRET": PayPayAPI_SECRET,
        "PayPay_MERCHANT_ID": PayPayMERCHANT_ID,
        'BT_ENVIRONMENT': BT_ENVIRONMENT,
        'BT_MERCHANT_ID': BT_MERCHANT_ID,
        'BT_PUBLIC_KEY': BT_PUBLIC_KEY,
        'BT_PRIVATE_KEY': BT_PRIVATE_KEY,
        'BT_APP_SECRET_KEY': BT_APP_SECRET_KEY,
        "auth": auths,
        "company_name": companyName,
        "company_email": companyEmail,
        "company_logo": companyLogo,
        "multiplier": multipliers,
        "min_input": min_input,
        "max_input": max_input,
        "Primary_Server_Address": primary_server,
        "main_message": main_message,
        "colour": colour,
    })
    session.commit()

    if PayPayAPI_KEY != '' or PayPayAPI_SECRET != '' or PayPayMERCHANT_ID != '':
        client = makeClient(PayPayAPI_KEY, PayPayAPI_SECRET, PayPayMERCHANT_ID)
        merchantPaymentId = uuid.uuid4().hex
        qr = {
            "merchantPaymentId": merchantPaymentId,
            "codeType": "ORDER_QR",
            "redirectUrl": "{}/{}".format("www.google.co.jp", merchantPaymentId),
            "redirectType": "WEB_LINK",
            "orderDescription": "Papercutポイントの追加購入",
            "orderItems": [{
                "name": "Verifying",
                "category": "Testing",
                "quantity": 1,
                "productId": "00001",
                "unitPrice": {
                        "amount": 1,
                        "currency": "JPY"
                }
            }],
            "amount": {
                "amount": 1,
                "currency": "JPY"
            },
        }

        response = client.Code.create_qr_code(qr)
        if (response["resultInfo"]["code"]) == 'SUCCESS':
            session.query(credentials).filter(credentials.id == 1).update({
                "mssg": "",
                "mssg_JP": "",
            })
            session.commit()
        else:
            session.query(credentials).filter(credentials.id == 1).update({
                "mssg": "Unable to make transaction, please check your credentials",
                "mssg_JP": "PayPayAPIもう一度確認",
            })
            session.commit()
        if primary_server != '' or auths != '':
            proxy = makeProxy(primary_server)
            auth = auths
            try:
                proxy.api.listUserAccounts(auth, 0, 10)
                session.query(credentials).filter(credentials.id == 1).update({
                    "mssg": "",
                    "mssg_JP": "",
                })
                session.commit()
            except:
                session.query(credentials).filter(credentials.id == 1).update({
                    "mssg": "Unable to make transaction, please check your credentials",
                    "mssg_JP": "PaperCut もう一度確認",
                })
                session.commit()
    adminSetting2 = session.query(credentials).first()
    response = {
        'message': 'update admin setting succeed',
        'credential': {
            'PayPay_API_KEY': adminSetting2.PayPay_API_KEY,
            'PayPay_API_SECRET': adminSetting2.PayPay_API_SECRET,
            'PayPay_MERCHANT_ID': adminSetting2.PayPay_MERCHANT_ID,
            'BT_ENVIRONMENT': adminSetting2.BT_ENVIRONMENT,
            'BT_MERCHANT_ID': adminSetting2.BT_MERCHANT_ID,
            'BT_PUBLIC_KEY': adminSetting2.BT_PUBLIC_KEY,
            'BT_PRIVATE_KEY': adminSetting2.BT_PRIVATE_KEY,
            'BT_APP_SECRET_KEY': adminSetting2.BT_APP_SECRET_KEY,
            "company_name": adminSetting2.company_name,
            "company_email": adminSetting2.company_email,
            "company_logo": adminSetting2.company_logo,
            'multiplier': adminSetting2.multiplier,
            'min_input': adminSetting2.min_input,
            'max_input': adminSetting2.max_input,
            'auth': adminSetting2.auth,
            'primary_server': adminSetting2.Primary_Server_Address,
            'mssg1': adminSetting2.mssg,
            'mssg2': adminSetting2.mssg2,
            'mssg_JP': adminSetting2.mssg_JP,
            'mssg2_JP': adminSetting2.mssg2_JP,
            'main_message': adminSetting2.main_message,
            'colour': adminSetting2.colour,
        }
    }
    session.close()
    return jsonify(response)


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.args.get('t')
        if not token:
            return jsonify({'message': 'Token is missing'}), 403
        try:
            data = jwt.decode(token, key, algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token expired, log in again'}), 403
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Invalid token. Please log in again.'}), 403

        return f(*args, **kwargs)
    return decorated


def generateToken(user, lang):
    adminSetting = session.query(credentials).first()
    proxy = makeProxy(adminSetting.Primary_Server_Address)
    auth = adminSetting.auth
    if proxy.api.isUserExists(auth, user) is True:
        expires = datetime.timedelta(hours=2)
        expires_refresh = datetime.timedelta(days=3)
        access_token = create_access_token(
            user, fresh=True, expires_delta=expires)
        data = jwt.encode({
            "data": user,
            "token_access": access_token
        }, key)
        session.close()
        if lang == 'jp':
            return redirect("{}/{}".format('/payment', ('?t='+data+'&lang=jp')))
        else:
            return redirect("{}/{}".format('/payment', ('?t='+data+'&lang=en')))
    else:
        session.close()
        return jsonify({'message': 'User Invalid'}), 403


def userTopUp(token, lang):
    tokens = jwt.decode(token, key, algorithms=['HS256'])
    user = tokens['data']
    access_token = tokens['token_access']
    if user == None:
        return jsonify({'message': 'User Invalid'}), 403
    else:
        if lang == 'jp':
            data = {
                'user': user,
                'jwt': access_token,
                'link': 'http://cosy-payment-demo.s3-website-ap-northeast-1.amazonaws.com/userpage/jp?token='+access_token
            }
            return jsonify(data)
        else:
            data = {
                'user': user,
                'jwt': access_token,
                'link': 'http://cosy-payment-demo.s3-website-ap-northeast-1.amazonaws.com/userpage?token='+access_token
            }
            return jsonify(data)
        # return redirect('http://localhost:3000/#/userpage/'+access_token)


def generatePageToken(user, lang):
    adminSetting = session.query(credentials).first()
    proxy = makeProxy(adminSetting.Primary_Server_Address)
    auth = adminSetting.auth
    if proxy.api.isUserExists(auth, user) is True:
        expires = datetime.timedelta(hours=2)
        expires_refresh = datetime.timedelta(days=3)
        access_token = create_access_token(
            user, fresh=True, expires_delta=expires)
        data = jwt.encode({
            "data": user,
            "token_access": access_token
        }, key)
        session.close()
        if lang == 'jp':
            return redirect("{}/{}".format('/paymentpage', ('?t='+data+'&lang=jp')))
        else:
            return redirect("{}/{}".format('/paymentpage', ('?t='+data+'&lang=en')))
    else:
        session.close()
        return jsonify({'message': 'User Invalid'}), 403


def userTopUpPage(token, lang):
    tokens = jwt.decode(token, key, algorithms=['HS256'])
    user = tokens['data']
    access_token = tokens['token_access']
    if user == None:
        return jsonify({'message': 'User Invalid'}), 403
    else:
        if lang == 'jp':
            return redirect('http://cosy-payment-demo.s3-website-ap-northeast-1.amazonaws.com/userpage/jp?token='+access_token)
        else:
            return redirect('http://cosy-payment-demo.s3-website-ap-northeast-1.amazonaws.com/userpage?token='+access_token)
