from django.contrib.auth import get_user_model, login, logout
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import generics
from rest_framework import permissions, status
from .serializers import UserRegisterSerializer, UserLoginSerializer, UserSerializer, UserVisitSerializer, VisitExtensionSerializer, VisitSerializer
from .validations import custom_validation, validate_email, validate_password
from .models import Visit, AppUser, VisitExtension
from datetime import datetime, timedelta
from django.db.models import Count
from django.shortcuts import get_object_or_404
from email.message import EmailMessage
from django.db.models import Q
from django.http import HttpResponse
import csv
import os
import logging
import smtplib
import ssl
import json
import mimetypes
import qrcode

# Inicjalizacja loggera
logger = logging.getLogger(__name__)
User = get_user_model()


class UserRegister(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        clean_data = custom_validation(request.data)
        serializer = UserRegisterSerializer(data=clean_data)
        if serializer.is_valid(raise_exception=True):
            user = serializer.create(clean_data)
            if user:
                return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(status=status.HTTP_400_BAD_REQUEST)


class UserLogin(APIView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = (SessionAuthentication,)

    ##
    def post(self, request):
        data = request.data
        assert validate_email(data)
        assert validate_password(data)
        serializer = UserLoginSerializer(data=data)
        if serializer.is_valid(raise_exception=True):
            user = serializer.check_user(data)
            login(request, user)
            # print(f"W post user login {serializer.data}")
            return Response(serializer.data, status=status.HTTP_200_OK)


class UserLogout(APIView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_200_OK)


class UserView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (SessionAuthentication,)

    ##
    def get(self, request):
        # print(f"Request: {request}")
        # print(f"Before serializer: {request.user}")
        serializer = UserSerializer(request.user)
        # print(f"After serializer: {serializer.data}")
        return Response({"user": serializer.data}, status=status.HTTP_200_OK)


class UserVisit(APIView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()

    def post(self, request):
        serializer = UserVisitSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            logger.info("Data saved successfully")

            # Generate link to change status
            visit_id = serializer.data.get("id")
            change_status_url = request.build_absolute_uri(
                f"/api/change_status/{visit_id}/"
            )

            # Sending email
            guest_email = request.data.get("guest_email", None)
            if guest_email:
                self.send_email_api(guest_email, serializer.data, change_status_url)

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            logger.error(f"Data validation error: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def send_email_api(self, guest_email, data, change_status_url):
        subject = "Zaplanowano wizytę w akademiku"
    
        # Formatowanie daty i godziny
        start_datetime = f"{data['start_date']} {data['start_time']}"
        end_datetime = f"{data['end_date']} {data['end_time']}"
    
        # Generowanie kodu QR
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(change_status_url)
        qr.make(fit=True)
        img = qr.make_image(fill='black', back_color='white')

        # Zapisanie obrazu kodu QR do pliku
        qr_filename = "change_status_qr.png"
        img.save(qr_filename)

        # Tworzenie wiadomości
        message = (
            f"Zaplanowano wizytę dla {data['guest_first_name']} {data['guest_last_name']} "
            f"w terminie od {start_datetime} do {end_datetime} w {data['dormitory']}.\n\n"
            #"Aby zmienic status wizyty na 'w trakcie', nacisnij link:\n"
            #f"{change_status_url}\n\n"
            "Aby rozpocząć wizytę, zeskanuj dołączony kod QR w kamerze przy recepcji"
        )
        from_email = os.environ.get("EMAIL")
        email_password = os.environ.get("EMAIL_PASSWORD")

        try:
            em = EmailMessage()
            em["From"] = from_email
            em["To"] = guest_email
            em["Subject"] = subject
            em.set_content(message)

            # Określenie typu MIME pliku
            ctype, encoding = mimetypes.guess_type(qr_filename)
            if ctype is None or encoding is not None:
                ctype = "application/octet-stream"
            maintype, subtype = ctype.split("/", 1)

            # Załączenie pliku kodu QR do wiadomości e-mail
            with open(qr_filename, "rb") as qr_file:
                em.add_attachment(qr_file.read(), maintype=maintype, subtype=subtype, filename=qr_filename)

            context = ssl.create_default_context()
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as smtp:
                smtp.login(from_email, email_password)
                smtp.send_message(em)
            logger.info(f"Email sent successfully to {guest_email}")
        except Exception as e:
            logger.error(f"Error sending email to {guest_email}: {e}")
        finally:
            # Usunięcie pliku kodu QR po wysłaniu wiadomości e-mail
            if os.path.exists(qr_filename):
                os.remove(qr_filename)

class ChangeStatus(APIView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()

    def get(self, request, visit_id):
        return self.change_status(request, visit_id)

    def post(self, request, visit_id):
        return self.change_status(request, visit_id)

    def change_status(self, request, visit_id):
        try:
            visit = Visit.objects.get(id=visit_id)
            visit.status = "Inprogress"
            visit.save()
            logger.info(f"Status for visit {visit_id} changed to inprogress")

            # Sending email notification
            guest_email = visit.guest_email
            if guest_email:
                self.send_status_changed_email(request, guest_email, visit)

            return Response({"status": "Inprogress"}, status=status.HTTP_200_OK)
        
        except Visit.DoesNotExist:
            logger.error(f"Visit with id {visit_id} does not exist")
            return Response(
                {"error": "Visit not found"}, status=status.HTTP_404_NOT_FOUND
            )
            
        except Exception as e:
            logger.error(f"Error changing status for visit {visit_id}: {e}")
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def send_status_changed_email(self, request, guest_email, visit):
        subject = "Wizyta w akademiku rozpoczęta"
        complete_visit_url = request.build_absolute_uri(
            f"/api/complete_visit/{visit.id}/"
        )

        # Generowanie kodu QR
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(complete_visit_url)
        qr.make(fit=True)
        img = qr.make_image(fill='black', back_color='white')

        # Zapisanie obrazu kodu QR do pliku
        qr_filename = "complete_visit_qr.png"
        img.save(qr_filename)

        # Tworzenie wiadomości
        message = (
            f"Status twojej wizyty {visit.id} zmienił się na trwająca.\n\n"
            #f"Aby zakończyć wizytę, naciśnij link:\n"
            #f"{complete_visit_url}\n\n"
            "Aby zakończyć wizytę, zeskanuj dołączony kod QR w kamerze przy recepcji."
        )
        from_email = os.environ.get("EMAIL")
        email_password = os.environ.get("EMAIL_PASSWORD")

        try:
            em = EmailMessage()
            em["From"] = from_email
            em["To"] = guest_email
            em["Subject"] = subject
            em.set_content(message)

            # Określenie typu MIME pliku
            ctype, encoding = mimetypes.guess_type(qr_filename)
            if ctype is None or encoding is not None:
                ctype = "application/octet-stream"
            maintype, subtype = ctype.split("/", 1)

            # Załączenie pliku kodu QR do wiadomości e-mail
            with open(qr_filename, "rb") as qr_file:
                em.add_attachment(qr_file.read(), maintype=maintype, subtype=subtype, filename=qr_filename)

            context = ssl.create_default_context()
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as smtp:
                smtp.login(from_email, email_password)
                smtp.send_message(em)
            logger.info(f"Email sent successfully to {guest_email}")
        except Exception as e:
            logger.error(f"Error sending email to {guest_email}: {e}")
        finally:
            # Usunięcie pliku kodu QR po wysłaniu wiadomości e-mail
            if os.path.exists(qr_filename):
                os.remove(qr_filename)


class CompleteVisit(APIView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()

    def get(self, request, visit_id):
        return self.complete_visit(request, visit_id)

    def post(self, request, visit_id):
        return self.complete_visit(request, visit_id)

    def complete_visit(self, request, visit_id):
        try:
            visit = Visit.objects.get(id=visit_id)
            visit.status = "Completed"
            visit.save()
            logger.info(f"Status for visit {visit_id} changed to completed")

            # Sending email notification
            guest_email = visit.guest_email
            if guest_email:
                self.send_status_completed_email(guest_email, visit)

            return Response({"status": "completed"}, status=status.HTTP_200_OK)
        except Visit.DoesNotExist:
            logger.error(f"Visit with id {visit_id} does not exist")
            return Response(
                {"error": "Visit not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error changing status for visit {visit_id}: {e}")
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def send_status_completed_email(self, guest_email, visit):
        subject = "Zakończono wizytę w akademiku"
        message = f"Status Twojej wizyty {visit.id} zmienił się na zakończoną."
        from_email = os.environ.get("EMAIL")
        email_password = os.environ.get("EMAIL_PASSWORD")

        try:
            em = EmailMessage()
            em["From"] = from_email
            em["To"] = guest_email
            em["Subject"] = subject
            em.set_content(message)
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as smtp:
                smtp.login(from_email, email_password)
                smtp.sendmail(from_email, guest_email, em.as_string())
            logger.info(f"Email sent successfully to {guest_email}")
        except Exception as e:
            logger.error(f"Error sending email to {guest_email}: {e}")
            
            
class CancelVisit(APIView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()

    def get(self, request, visit_id):
        return self.cancel_visit(request, visit_id)

    def post(self, request, visit_id):
        return self.cancel_visit(request, visit_id)

    def cancel_visit(self, request, visit_id):
        try:
            visit = Visit.objects.get(id=visit_id)
            visit.status = "Cancelled"
            visit.save()
            logger.info(f"Status for visit {visit_id} changed to cancelled")

            # Sending email notification
            guest_email = visit.guest_email
            if guest_email:
                self.send_status_cancelled_email(guest_email, visit)

            return Response({"status": "Cancelled"}, status=status.HTTP_200_OK)
        except Visit.DoesNotExist:
            logger.error(f"Visit with id {visit_id} does not exist")
            return Response(
                {"error": "Visit not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error changing status for visit {visit_id}: {e}")
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def send_status_cancelled_email(self, guest_email, visit):
        subject = "Anulowano Twoją wizytę w akademiku"
        message = f"Status twojej wizyty {visit.id}, gość: {visit.guest_first_name} {visit.guest_last_name} zmienił się na anulowaną."
        from_email = os.environ.get("EMAIL")
        email_password = os.environ.get("EMAIL_PASSWORD")

        try:
            em = EmailMessage()
            em["From"] = from_email
            em["To"] = guest_email
            em["Subject"] = subject
            em.set_content(message)
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as smtp:
                smtp.login(from_email, email_password)
                smtp.sendmail(from_email, guest_email, em.as_string())
            logger.info(f"Email sent successfully to {guest_email}")
        except Exception as e:
            logger.error(f"Error sending email to {guest_email}: {e}")


class AdminCancelVisit(APIView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()

    def get(self, request, visit_id):
        return self.cancel_visit(request, visit_id)

    def post(self, request, visit_id):
        return self.cancel_visit(request, visit_id)

    def cancel_visit(self, request, visit_id):
        try:
            visit = Visit.objects.get(id=visit_id)
            visit.status = "Expelled"
            description = request.data.get("description", "Wizyta została anulowana przez administratora")
            visit.description = description
            visit.save()
            logger.info(f"Status for visit {visit_id} changed to Expelled")

            # Sending email notification
            guest_email = visit.guest_email
            if guest_email:
                self.send_status_cancelled_email(guest_email, visit)

            return Response({"status": "expelled"}, status=status.HTTP_200_OK)
        except Visit.DoesNotExist:
            logger.error(f"Visit with id {visit_id} does not exist")
            return Response(
                {"error": "Visit not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error changing status for visit {visit_id}: {e}")
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def send_status_cancelled_email(self, guest_email, visit):
        subject = "Zostałeś wydalony z akademika"
        message = f"Twoja wizyta została anulowana przez administratora {visit.id}, gość: {visit.guest_first_name} {visit.guest_last_name}. Powód: {visit.description}"
        from_email = os.environ.get("EMAIL")
        email_password = os.environ.get("EMAIL_PASSWORD")

        try:
            em = EmailMessage()
            em["From"] = from_email
            em["To"] = guest_email
            em["Subject"] = subject
            em.set_content(message)
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as smtp:
                smtp.login(from_email, email_password)
                smtp.sendmail(from_email, guest_email, em.as_string())
            logger.info(f"Email sent successfully to {guest_email}")
        except Exception as e:
            logger.error(f"Error sending email to {guest_email}: {e}")


class VisitListView(generics.ListAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (SessionAuthentication,)
    serializer_class = UserVisitSerializer

    def get(self, request):
        try:
            if request.user.is_authenticated:
                queryset = Visit.objects.filter(user=request.user.user_id)
                print(queryset)
                serializer = self.serializer_class(queryset, many=True)
                return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AllVisitListView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (SessionAuthentication,)

    def get(self, request):
        try:
            print(request.user.is_authenticated)
            print(request.user.is_community_member)
            
            if not request.user.is_authenticated:
                print("a")
                return Response(
                    {"error": "User not authenticated"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            if not request.user.is_receptionist and not request.user.is_community_member:
                return Response(
                    {"error": "User is neither a receptionist nor a community member"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            print(request.user.dormitory)
            visits = Visit.objects.filter(dormitory=request.user.dormitory)
            serializer = UserVisitSerializer(visits, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"Error fetching visit list: {e}")
            logger.error(f"Error fetching visit list: {e}")
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class RequestVisitExtension(APIView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()

    def post(self, request):
        logger.info(f"Received data: {request.data}")
        serializer = VisitExtensionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            logger.info("Data saved successfully")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            logger.error(f"Data validation error: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AllVisitExtensionListView(APIView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()

    def get(self, request):
        try:
            if request:
                if request:
                    requests = VisitExtension.objects.all()
                    serializer = VisitExtensionSerializer(requests, many=True)
                    return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ApproveRejectExtension(APIView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()

    def put(self, request, extension_id, action):
        try:
            extension = VisitExtension.objects.get(pk=extension_id)
        except VisitExtension.DoesNotExist:
            return Response(
                {"error": "Extension not found"}, status=status.HTTP_404_NOT_FOUND
            )

        comment = request.data.get("comment", "")

        if action == "approve":
            extension.status = "Approved"
            extension.visit.extend_visit()
            self.send_email_api(
                extension.visit.guest_email, "Twoja przedłużka została zaakceptowana."
            )
        elif action == "reject":
            extension.status = "Rejected"
            self.send_email_api(
                extension.visit.guest_email, f"Twoja przedłużka została odrzucona. Powód: {comment}"
            )
        else:
            return Response(
                {"error": "Invalid action"}, status=status.HTTP_400_BAD_REQUEST
            )

        extension.comment = comment
        extension.save()
        return Response(
            VisitExtensionSerializer(extension).data, status=status.HTTP_200_OK
        )

    def send_email_api(self, guest_email, message):
        subject = "Zmieniono status przedłużenia"
        message = message
        from_email = os.environ.get("EMAIL")
        email_password = os.environ.get("EMAIL_PASSWORD")

        try:
            em = EmailMessage()
            em["From"] = from_email
            em["To"] = guest_email
            em["Subject"] = subject
            em.set_content(message)
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as smtp:
                smtp.login(from_email, email_password)
                smtp.sendmail(from_email, guest_email, em.as_string())
            logger.info(f"Email sent successfully to {guest_email}")
        except Exception as e:
            logger.error(f"Error sending email to {guest_email}: {e}")


class UserDetailView(generics.RetrieveAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = (permissions.IsAuthenticated,)

class HostVisitsView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (SessionAuthentication,)

    def get(self, request, user_id):
        try:
            visits = Visit.objects.filter(user_id=user_id)
            if not visits.exists():
                return Response({'error': 'No guests found for this user.'}, status=status.HTTP_404_NOT_FOUND)

            if 'download' in request.GET:
                response = HttpResponse(content_type='text/csv')
                response['Content-Disposition'] = 'attachment; filename="guest_list.csv"'

                writer = csv.writer(response)
                writer.writerow(['ID', 'Guest First Name', 'Guest Last Name', 'Start Date'])
                for visit in visits:
                    writer.writerow([visit.id, visit.guest_first_name, visit.guest_last_name, visit.start_date])

                return response

            serializer = VisitSerializer(visits, many=True)
            return Response({'guests': serializer.data}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ReceptionStatsView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (SessionAuthentication,)

    def get(self, request):
        try:
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')

            if start_date and end_date:
                stats_queryset = Visit.objects.filter(
                    start_date__range=[start_date, end_date]
                ).values("status").annotate(count=Count("status"))
            else:
                stats_queryset = Visit.objects.values("status").annotate(count=Count("status"))

            all_statuses = ['inprogress', 'cancelled', 'completed', 'pending', 'expelled']
            stats = {status: 0 for status in all_statuses}

            for item in stats_queryset:
                stats[item['status'].lower()] = item['count']

            if request.GET.get('download') == 'true':
                response = HttpResponse(content_type='text/csv')
                response['Content-Disposition'] = 'attachment; filename="reception_stats.csv"'

                writer = csv.writer(response)
                writer.writerow(['Rodzaj', 'Wartość'])
                writer.writerow(['Data początkowa', start_date])
                writer.writerow(['Data końcowa', end_date])

                for key, value in stats.items():
                    writer.writerow([key, value])

                return response

            translated_stats = {
                'inprogress': 'Wizyty w toku',
                'cancelled': 'Anulowane wizyty',
                'completed': 'Zakończone wizyty',
                'pending': 'Oczekujące wizyty',
                'expelled': 'Wydalone wizyty'
            }

            response = {translated_stats.get(key, key): value for key, value in stats.items()}
            return Response(response)
        except Exception as e:
            return Response({'error': str(e)}, status=500)

class MonthlyReportView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (SessionAuthentication,)

    def get(self, request):
        try:
            start_date_str = request.GET.get('start_date')
            end_date_str = request.GET.get('end_date')

            if not start_date_str or not end_date_str:
                return Response({'error': 'Start date and end date are required.'}, status=status.HTTP_400_BAD_REQUEST)

            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')

            visits = Visit.objects.filter(start_date__range=(start_date, end_date))

            if not visits.exists():
                return Response({'error': 'No visits found for this period.'}, status=status.HTTP_404_NOT_FOUND)

            stats = visits.values('start_date').annotate(total=Count('id'))
            return Response(stats, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class UserSearchView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (SessionAuthentication,)

    def get(self, request):
        query = request.GET.get('q', '')

        if query:
            users = User.objects.filter(
                Q(user_id__icontains=query) |
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query) |
                Q(email__icontains=query) |
                Q(room_number__icontains=query)
            )
            results = [{'id': user.user_id, 'first_name': user.first_name, 'last_name': user.last_name, 'email': user.email, 'room_number': user.room_number} for user in users]
            return Response(results, status=status.HTTP_200_OK)
        return Response({'error': 'No query provided'}, status=status.HTTP_400_BAD_REQUEST)

class HostVisitsDownloadView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (SessionAuthentication,)

    def get(self, request, user_id):
        try:
            visits = Visit.objects.filter(user_id=user_id)
            if not visits.exists():
                return Response({'error': 'No guests found for this user.'}, status=status.HTTP_404_NOT_FOUND)

            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="Lista_gości_dla_hosta.csv"'

            writer = csv.writer(response)
            writer.writerow(['ID', 'Guest First Name', 'Guest Last Name', 'Start Date'])
            for visit in visits:
                writer.writerow([visit.id, visit.guest_first_name, visit.guest_last_name, visit.start_date])

            return response
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ReceptionStatsDownloadView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (SessionAuthentication,)

    def get(self, request):
        try:
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')

            if start_date and end_date:
                visits = Visit.objects.filter(start_date__range=[start_date, end_date])
            else:
                visits = Visit.objects.all()

            stats = visits.values('status').annotate(count=Count('status'))
            total_visits = visits.count()

            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="Statystyki_aktywności_recepcji_{start_date}_do_{end_date}.csv"'

            writer = csv.writer(response)
            writer.writerow(['Start Date', 'End Date'])
            writer.writerow([start_date, end_date])
            writer.writerow([])
            writer.writerow(['Status', 'Count'])
            for stat in stats:
                writer.writerow([stat['status'], stat['count']])
            writer.writerow(['Total', total_visits])

            return response
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class MonthlyReportDownloadView(APIView):
    permission_classes = (permissions.IsAuthenticated,)
    authentication_classes = (SessionAuthentication,)

    def get(self, request):
        try:
            start_date_str = request.GET.get('start_date')
            end_date_str = request.GET.get('end_date')

            if not start_date_str or not end_date_str:
                return Response({'error': 'Start date and end date are required.'}, status=status.HTTP_400_BAD_REQUEST)

            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')

            visits = Visit.objects.filter(start_date__range=(start_date, end_date))

            if not visits.exists():
                return Response({'error': 'No visits found for this period.'}, status=status.HTTP_404_NOT_FOUND)

            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="Raport_wizyt_w_wybranym_okresie_{start_date_str}_do_{end_date_str}.csv"'

            writer = csv.writer(response)
            writer.writerow(['Start Date', 'End Date'])
            writer.writerow([start_date_str, end_date_str])
            writer.writerow([])
            writer.writerow(['ID', 'Start Date', 'End Date', 'Status'])
            for visit in visits:
                writer.writerow([visit.id, visit.start_date, visit.end_date, visit.status])

            return response
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# class VisitListView(generics.ListCreateAPIView):
#     permission_classes = (permissions.IsAuthenticated,)
#     authentication_classes = (SessionAuthentication,)
#     queryset = Visit.objects.all()
#     serializer_class = VisitSerializer

#     def list(self, request):
#         queryset = self.get_queryset()
#         serializer = UserSerializer(queryset, many=True)
#         return Response({serializer.data}, status=status.HTTP_200_OK)

# class VisitDetailView(generics.RetrieveUpdateDestroyAPIView):
#     permission_classes = (permissions.IsAuthenticated,)
#     authentication_classes = (SessionAuthentication,)
#     queryset = Visit.objects.all()
#     serializer_class = VisitSerializer

#     def list(self, request):
#         queryset = self.get_queryset()
#         serializer = UserSerializer(queryset, many=True)
#         return Response({serializer.data}, status=status.HTTP_200_OK)

# class VisitFormView(APIView):
#     def upload_form(request):
#         form = VisitForm(request.POST)
