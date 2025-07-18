from ...ui import load_image_with_callback 
from ...utility.system import open_website
from gi.repository import Gtk, Pango, GObject

class WebSearchWidget(Gtk.Box):
    __gsignals__ = {
        'website-clicked': (GObject.SignalFlags.RUN_LAST, None, (str,))
    }

    def __init__(self, search_term, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10, **kwargs)
        self.add_css_class("osd")
        self.add_css_class("toolbar")
        self.add_css_class("code")
        self.set_margin_top(10)
        self.set_margin_bottom(10)
        self.set_margin_start(12)
        self.set_margin_end(12)

        self._search_term = search_term
        self._website_widgets = []
        self._current_spinner_revealer = None
        self._current_spinner = None
        self._is_first_website = True

        # 1. Initial Status Label - Remains visible
        self._status_label = Gtk.Label(
            label=f"Searching for \"{self._search_term}\"...",
            halign=Gtk.Align.START,
        )
        self._status_label.add_css_class("pulsing-label")
        self._status_label.add_css_class("heading")
        self.append(self._status_label)

        # 2. Container for website list
        self._website_list_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=5,
            margin_top=5,
            margin_bottom=5
        )
        self.append(self._website_list_box)

        # 3. Expander for the final result (initially hidden)
        self._result_label = Gtk.Label(
            wrap=True,
            wrap_mode=Pango.WrapMode.WORD_CHAR,
            justify=Gtk.Justification.LEFT,
            selectable=True,
            margin_top=6,
            margin_bottom=6,
            margin_start=6,
            margin_end=6,
        )
        self._expander = Gtk.Expander(label="Search Result")
        self._expander.set_child(self._result_label)
        self._expander.set_expanded(False)
        self._expander.set_visible(False)
        self.append(self._expander)

    def _create_website_row(self, title, link, favicon):
        if not favicon.startswith("http") and not favicon.startswith("https"):
            from urllib.parse import urlparse, urljoin
            base_url = urlparse(link).scheme + "://" + urlparse(link).netloc
            favicon = urljoin(base_url, favicon)
            print(favicon)
        button = Gtk.Button()
        button.connect("clicked", lambda x, link=link: self.emit('website-clicked', link))
        row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        icon = Gtk.Image(icon_name="internet-symbolic")
        load_image_with_callback(favicon, lambda pixbuf_loader: icon.set_from_pixbuf(pixbuf_loader.get_pixbuf()))
        row_box.append(icon)
        label = Gtk.Label(label=title, halign=Gtk.Align.START, tooltip_text=link, hexpand=True, ellipsize=Pango.EllipsizeMode.END)
        row_box.append(label)
        spinner_revealer = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_LEFT, transition_duration=250, reveal_child=False)
        spinner = Gtk.Spinner(tooltip_text="Fetching...")
        spinner_revealer.set_child(spinner)
        row_box.append(spinner_revealer)
        button.set_child(row_box)
        return button, spinner, spinner_revealer
 
    # add_website remains the same
    def add_website(self, title, link, favicon_path=None):
        if self._current_spinner_revealer and self._current_spinner:
            self._current_spinner.stop()
        if self._is_first_website:
            self._is_first_website = False
        row_box, new_spinner, new_spinner_revealer = self._create_website_row(title, link, favicon_path)
        self._current_spinner = new_spinner
        self._current_spinner_revealer = new_spinner_revealer
        row_revealer = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.SLIDE_UP, transition_duration=300)
        row_revealer.set_child(row_box)
        self._website_list_box.append(row_revealer)
        row_revealer.set_reveal_child(True)
        self._current_spinner.start()
        self._current_spinner_revealer.set_reveal_child(True)
        self._website_widgets.append(row_revealer)

    # finish remains the same
    def finish(self, result_text):
        self._status_label.remove_css_class("pulsing-label")
        if self._is_first_website:
            self._is_first_website = False
        if self._current_spinner_revealer and self._current_spinner:
            self._current_spinner.stop()
            self._current_spinner_revealer.set_reveal_child(False)
            self._current_spinner = None
            self._current_spinner_revealer = None
        self._result_label.set_text(result_text)
        self._expander.set_visible(True)
        self._expander.set_expanded(False)
