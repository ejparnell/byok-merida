# Use persistent web-page access for Extension Capture

Merida's side panel must still capture a new Source Page after the user navigates without requiring the panel to close and reopen. Extension Capture will therefore use persistent all-sites HTTP(S) host access at installation rather than rely only on Chrome's temporary `activeTab` grant; the smoother browsing workflow outweighs the broader permission. Chrome-internal and other non-web pages remain unreadable, and capture remains an explicit **Fill Form** action.
