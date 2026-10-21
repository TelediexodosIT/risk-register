from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class Company(models.Model):
    """A customer company. Every assessment, task and user belongs to one."""

    name = models.CharField(max_length=150, unique=True)
    sector = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "companies"

    def __str__(self):
        return self.name


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.update(is_staff=True, is_superuser=True, role=User.Role.CONSULTANT)
        return self._create_user(email, password, **extra)


class User(AbstractUser):
    """People sign in with their email address. There is no username."""

    class Role(models.TextChoices):
        CONSULTANT = "consultant", "Consultant"
        SAFETY_OFFICER = "safety_officer", "Safety officer"
        MEMBER = "member", "Staff member"

    username = None
    email = models.EmailField(unique=True)
    job_title = models.CharField(max_length=100, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)
    company = models.ForeignKey(
        Company, null=True, blank=True, on_delete=models.PROTECT, related_name="users",
        help_text="The company this person works for.",
    )
    managed_companies = models.ManyToManyField(
        Company, blank=True, related_name="consultants",
        help_text="Consultants only: the client companies this person can see and manage.",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()

    class Meta:
        ordering = ["first_name", "last_name"]

    def __str__(self):
        return self.get_full_name() or self.email

    @property
    def is_consultant(self):
        return self.role == self.Role.CONSULTANT

    @property
    def can_manage(self):
        """Consultants and safety officers can create and edit assessments."""
        return self.role in (self.Role.CONSULTANT, self.Role.SAFETY_OFFICER)

    def visible_companies(self):
        """The only companies this user may see. Every view filters through this."""
        if self.is_superuser:
            return Company.objects.filter(is_active=True)
        if self.is_consultant:
            ids = set(self.managed_companies.values_list("id", flat=True))
            if self.company_id:
                ids.add(self.company_id)
            return Company.objects.filter(id__in=ids, is_active=True)
        return Company.objects.filter(id=self.company_id, is_active=True)

    @property
    def initials(self):
        parts = [p for p in (self.first_name, self.last_name) if p]
        return "".join(p[0] for p in parts).upper() or self.email[:2].upper()
