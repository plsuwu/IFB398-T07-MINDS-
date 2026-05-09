from django import forms
from django.forms import ModelForm
from .models import Document, Process, Prospect, Tenement
from .tagging import TAG_CHOICES

class DocumentForm(ModelForm):
    timestamp = forms.DateField(
        required=False,
        input_formats=[
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%d-%m-%Y",
        ],
        widget=forms.DateInput(attrs={"type": "date"}),
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
            "tenement", "commodity", "reporting_stage", "author_name",
        ]
        widgets = {
            "commodity": forms.TextInput(attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-cyan-500 text-sm",
                "placeholder": "e.g. Gold, Copper",
            }),
            "author_name": forms.TextInput(attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-cyan-500 text-sm",
                "placeholder": "Author name",
            }),
        }

    def __init__(self, *args, organisation=None, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.initial["tags"] = self.instance.tags or []
        if organisation:
            self.fields["tenement"].queryset = Tenement.objects.filter(
                organisation=organisation
            ).order_by("name")
        else:
            self.fields["tenement"].queryset = Tenement.objects.none()
        self.fields["tenement"].required = False
        self.fields["tenement"].empty_label = "— None —"
        self.fields["reporting_stage"].required = False

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
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "placeholder": "Search by title, type, project, organisation...",
            "class": _INPUT,
        }),
    )
    process = forms.ModelChoiceField(
        queryset=Process.objects.order_by("name"),
        required=False,
        empty_label="All projects",
        widget=forms.Select(attrs={"class": _INPUT}),
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": _INPUT}),
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": _INPUT}),
    )
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
    tenement = forms.ModelChoiceField(
        queryset=Tenement.objects.none(),
        required=False,
        empty_label="All tenements",
        widget=forms.Select(attrs={"class": _INPUT}),
    )
    commodity = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": _INPUT, "placeholder": "Commodity"}),
    )
    author_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": _INPUT, "placeholder": "Author name"}),
    )
    reporting_stage = forms.ChoiceField(
        choices=[],
        required=False,
        widget=forms.Select(attrs={"class": _INPUT}),
    )

    def __init__(self, *args, doc_type_choices=None, organisation=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["doc_type"].choices = doc_type_choices or [("", "All types")]
        self.fields["reporting_stage"].choices = (
            [("", "All stages")] + Document.REPORTING_STAGE_CHOICES
        )
        if organisation:
            self.fields["tenement"].queryset = Tenement.objects.filter(
                organisation=organisation
            ).order_by("name")

    def clean(self):
        cleaned = super().clean()
        d_from = cleaned.get("date_from")
        d_to = cleaned.get("date_to")
        if d_from and d_to and d_from > d_to:
            raise forms.ValidationError("'From' date cannot be after 'To' date.")
        return cleaned


class TenementForm(ModelForm):
    geom_geojson = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = Tenement
        fields = ["name", "process"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-cyan-500 text-sm",
                "placeholder": "e.g. EPM 27431",
            }),
        }

    def __init__(self, *args, organisation=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._organisation = organisation
        if organisation:
            self.fields["process"].queryset = Process.objects.filter(
                organisation=organisation
            ).order_by("name")
        else:
            self.fields["process"].queryset = Process.objects.none()
        self.fields["process"].label = "Project"
        self.fields["process"].empty_label = "Select a project..."

    def _post_clean(self):
        from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Polygon
        if self._organisation is not None:
            self.instance.organisation = self._organisation
        geojson = (self.cleaned_data or {}).get("geom_geojson", "").strip()
        if geojson:
            try:
                geom = GEOSGeometry(geojson)
                if isinstance(geom, Polygon):
                    geom = MultiPolygon(geom)
                self.instance.geom = geom
            except Exception:
                self.add_error("geom_geojson", "Invalid geometry — please redraw the boundary.")
        super()._post_clean()


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
        self._organisation = organisation  # stored for _post_clean
        if organisation:
            self.fields["process"].queryset = Process.objects.filter(
                organisation=organisation
            ).order_by("name")
        if initial_process:
            self.fields["process"].initial = initial_process
        self.fields["process"].label = "Project"
        self.fields["process"].empty_label = "Select a project..."

    def _post_clean(self):
        from django.contrib.gis.geos import Point
        # Pre-populate fields that are set by the view (not form fields) so that
        # Prospect.save() → full_clean() (called with no exclusions) does not fail.
        if self._organisation is not None:
            self.instance.organisation = self._organisation
        lat = (self.cleaned_data or {}).get("latitude")
        lng = (self.cleaned_data or {}).get("longitude")
        if lat is not None and lng is not None:
            self.instance.geom = Point(float(lng), float(lat), srid=4326)
        elif not self.instance.geom:
            self.instance.geom = Point(0.0, 0.0, srid=4326)
        super()._post_clean()