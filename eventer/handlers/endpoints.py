import logging
from base64 import b64decode
from urllib.parse import parse_qs

import bcrypt
import simplejson
import tornado.gen
from mongoengine.errors import NotUniqueError, DoesNotExist

from eventer.handlers.base import HttpPageHandler, AuthenticationRequiredHandler
from eventer.models import User, EventCategory
from eventer.errors import CategoryValidationError
from eventer.util import generate_uuid_token


class RegisterEndpointHandler(HttpPageHandler):
    @tornado.gen.coroutine
    def validate_username_and_email(self, username, email):
        result = []
        username_valid = User.objects(username__exact=username).count()
        if username_valid:
            result.append("Username already taken")
        email_valid = User.objects(email__exact=email).count()
        if email_valid:
            result.append("Email already in use")
        return result

    @tornado.gen.coroutine
    def persist_user(self, username, password, first_name, last_name, email):
        user_instance = User()
        user_instance.username = username
        user_instance.password = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
        user_instance.first_name = first_name
        user_instance.last_name = last_name
        user_instance.email = email
        user_instance.save()

        return user_instance

    @tornado.gen.coroutine
    def post(self, *args, **kwargs):
        username = self.get_body_argument("username", None)
        password = self.get_body_argument("password", None)
        first_name = self.get_body_argument("first_name", None)
        last_name = self.get_body_argument("last_name", None)
        email = self.get_body_argument("email", None)

        errors = []
        if not username:
            errors.append("Username is mandatory")

        if not email:
            errors.append("Email is mandatory")

        if not password:
            errors.append("Password is mandatory")

        if not first_name:
            errors.append("First name is mandatory")

        if not last_name:
            errors.append("Last name is mandatory")

        validate_result_errors = yield self.validate_username_and_email(username, email)
        if validate_result_errors:
            errors.extend(validate_result_errors)

        if errors:
            self.set_status(400, simplejson.dumps({"success": False, "errors": errors}))
            return

        registered_user = yield self.persist_user(username, password, first_name, last_name, email)
        logging.debug("Registered used: {}".format(registered_user.id))
        registered_user.session_token = generate_uuid_token()
        registered_user.save()
        self.set_secure_cookie("Session", registered_user.session_token)
        self.set_header("Content-Type", "application/json")
        self.write(simplejson.dumps({"success": True}))


class AuthenticationEndpointHandler(HttpPageHandler):
    @tornado.gen.coroutine
    def validate_username_and_password(self, username, password):
        try:
            user = User.objects.get(username=username)
        except DoesNotExist:
            logging.error("Invalid username")
            return False
        else:
            return bcrypt.checkpw(password.encode(), user.password)

    @tornado.gen.coroutine
    def post(self):
        if self.get_current_user():
            self.set_status(403, "Already authenticated")
            return

        username = self.get_body_argument("username")
        password = self.get_body_argument("password")
        is_valid = yield self.validate_username_and_password(username, password)
        if is_valid:
            new_token = generate_uuid_token()
            target_user = User.objects.get(username=username)
            target_user.session_token = new_token
            target_user.save()
            self.set_secure_cookie("Session", new_token)
            self.write(simplejson.dumps({"success": True}))
        else:
            self.set_status(403, "Invalid username or password")


class LogoutEndpointHandler(HttpPageHandler):
    @tornado.gen.coroutine
    def post(self):
        current_user = self.get_current_user()
        current_user.session_token = None
        current_user.save()
        self.write(simplejson.dumps({"success": True}))


class CreateCategoryEndpointHandler(AuthenticationRequiredHandler):
    @tornado.gen.coroutine
    def post(self):
        name = self.get_body_argument("name")
        description = self.get_body_argument("description")
        values = [simplejson.loads(b64decode(x.encode()).decode()) for x in self.get_body_arguments("fields[]")]

        for value in values:
            parsed = parse_qs(value["constraints"])
            value["constraints"] = {k: parsed[k][0] for k in parsed}

        try:
            for field in values:
                EventCategory.field_is_valid(field)
        except CategoryValidationError as e:
            logging.error(e)
            self.write(simplejson.dumps({"success": False, "error": str(e)}))
        else:
            category = EventCategory(name=name, description=description, user=self.current_user, fields=values)
            category.save()
            self.write(simplejson.dumps({"success": True, "id": str(category.id)}))
