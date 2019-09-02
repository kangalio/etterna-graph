# Approches to model the various plots

* Single big class with special-case-ifs for everything
    * Bad: hard to read/maintain

* Small base class for scatter charts, subclasses for the rest<br/>
    * (Bad: partly repeated code in overwriting functions)
    * Bad: No combining of differences
