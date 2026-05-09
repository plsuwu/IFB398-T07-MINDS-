from django import forms
from django.forms import ModelForm
from .models import Document, Process, Prospect
from .tagging import TAG_CHOICES

class DocumentForm(ModelForm):
    timestamp = forms.DateField(
        required=False,
        input_formats=[
            "%Y-%m-%d",   # 2025-10-12  (default, ISO)
            "%d/%m/%Y",   # 12/10/2025
            "%d-%m-%Y",   # 12-10-2025
        ],
        widget=forms.DateInput(attrs={"type": "date"}), # HTML5 picker
        label="Date"
    )
    
    tags = forms.TypedMultipleChoiceField(
        choices=TAG_CHOICES,
        coerce=int,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Tags",
    )

    class Meta:
        model = Document
        fields = [
            "title", "file", "organisation", "process",
            "timestamp", "doc_type", "confidentiality", "tags",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial["tags"] = self.instance.tags or []

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.tags = list(map(int, self.cleaned_data.get("tags", [])))
        if commit:
            obj.save()
        return obj

# ---- Search Form ------
 
CONFIDENTIALITY_CHOICES = [
    ("", "Any"),
    ("public", "Public"),
    ("internal", "Internal"),
    ("confidential", "Confidential"),
]

TAG_FILTER_CHOICES = [("", "Any tag")] + TAG_CHOICES

_INPUT = "w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-cyan-500 text-sm"

class DocumentSearchForm(forms.Form):
    # Full-text keyword - searched title, type, org, project
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "placeholder": "Search by title, type, project, organisation...",
            "class": _INPUT,
        }),
    )

    # Project / process filter
    process = forms.ModelChoiceField(
        queryset=Process.objects.order_by("name"),
        required=False,
        empty_label="All projects",
        widget=forms.Select(attrs={"class": _INPUT}),
    )
 
    # Date range — filters on the document's own date (timestamp), not upload date
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": _INPUT}),
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": _INPUT}),
    )
 
    # Metadata filters
    doc_type = forms.ChoiceField(
        choices=[],
        required=False,
        widget=forms.Select(attrs={"class": _INPUT}),
    )
    confidentiality = forms.ChoiceField(
        choices=CONFIDENTIALITY_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": _INPUT}),
    )
    tag = forms.ChoiceField(
        choices=TAG_FILTER_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": _INPUT}),
    )

    def __init__(self, *args, doc_type_choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["doc_type"].choices = doc_type_choices or [("", "All types")]

    def clean(self):
        cleaned = super().clean()
        d_from = cleaned.get("date_from")
        d_to = cleaned.get("date_to")
        if d_from and d_to and d_from > d_to:
            raise forms.ValidationError("'From' date cannot be after 'To' date.")
        return cleaned


class ProspectForm(ModelForm):
    latitude = forms.DecimalField(
        max_digits=10, decimal_places=7, required=True,
        widget=forms.HiddenInput(),
        error_messages={"required": "A mapped location is required. Click on the map to place a pin."}
    )
    longitude = forms.DecimalField(
        max_digits=10, decimal_places=7, required=True,
        widget=forms.HiddenInput(),
    )

    class Meta:
        model = Prospect
        fields = ["name", "process", "hypothesis", "objective"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-cyan-500 text-sm",
                "placeholder": "e.g. Ridgeline East",
            }),
            "hypothesis": forms.Textarea(attrs={
                "rows": 5,
                "class": "w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-cyan-500 text-sm",
                "placeholder": "Describe the geological hypothesis. What do you believe is here and why?",
            }),
            "objective": forms.Textarea(attrs={
                "rows": 4,
                "class": "w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-cyan-500 text-sm",
                "placeholder": "State the exploration objective. What will you do to test the hypothesis?",
            }),
        }

    def __init__(self, *args, organisation=None, initial_process=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organisation:
            self.fields["process"].queryset = Process.objects.filter(
                organisation=organisation
            ).order_by("name")
        if initial_process:
            self.fields["process"].initial = initial_process
        self.fields["process"].label = "Project"
        self.fields["process"].empty_label = "Select a project..."