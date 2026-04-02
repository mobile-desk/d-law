from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm

User = get_user_model()


class EmailAuthenticationForm(AuthenticationForm):
    remember_me = forms.BooleanField(
        required=False,
        initial=True,
        label="Stay signed in on this device",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Email"
        self.fields["username"].widget.attrs.update(
            {
                "autocomplete": "email",
                "class": "auth-input",
                "placeholder": "you@example.com",
            }
        )
        self.fields["password"].widget.attrs.update(
            {
                "autocomplete": "current-password",
                "class": "auth-input",
                "placeholder": "Enter your password",
            }
        )
        self.fields["remember_me"].label = ""


class RegisterForm(forms.ModelForm):
    password = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput(
            attrs={"autocomplete": "new-password", "class": "auth-input", "placeholder": "At least 8 characters"}
        ),
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(
            attrs={"autocomplete": "new-password", "class": "auth-input", "placeholder": "Repeat password"}
        ),
        label="Confirm password",
    )

    class Meta:
        model = User
        fields = ("email", "phone")
        widgets = {
            "email": forms.EmailInput(
                attrs={"autocomplete": "email", "class": "auth-input", "placeholder": "you@example.com"}
            ),
            "phone": forms.TextInput(
                attrs={"autocomplete": "tel", "class": "auth-input", "placeholder": "Optional — for urgent contact"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].label = "Email"
        self.fields["phone"].label = "Phone"
        self.fields["phone"].required = False

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        data = super().clean()
        p1 = data.get("password")
        p2 = data.get("password_confirm")
        if p1 and p2 and p1 != p2:
            self.add_error("password_confirm", "Passwords do not match.")
        return data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.user_type = "user"
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user
