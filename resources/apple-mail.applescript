on linesOf(itemsList)
    set oldTids to AppleScript's text item delimiters
    set AppleScript's text item delimiters to linefeed
    set valueText to itemsList as text
    set AppleScript's text item delimiters to oldTids
    return valueText
end linesOf
on run argv
    set op to item 1 of argv
    tell application "Mail"
        launch
        if op is "konten" then return my linesOf(name of accounts)
        set accountName to item 2 of argv
        set matches to every account whose name is accountName
        if (count matches) is not 1 then error "Mailkonto nicht eindeutig."
        set acct to first item of matches
        if op is "ordner" then return my linesOf(name of mailboxes of acct)
        set boxName to item 3 of argv
        set boxRef to mailbox boxName of acct
        if op is "liste" then
            check for new mail for acct
            set cutoff to (current date) - ((item 4 of argv) as integer)
            return my linesOf(message id of (messages of boxRef whose date received ≥ cutoff))
        end if
        set mid to item 4 of argv
        set msgs to messages of boxRef whose message id is mid
        if op is "anzahl" then return count msgs
        if op is "ablage" then
            set targetAcctName to item 5 of argv
            set targetAccts to every account whose name is targetAcctName
            if (count targetAccts) is not 1 then error "Zielkonto nicht eindeutig."
            set targetBox to mailbox (item 6 of argv) of (first item of targetAccts)
            set oldCopies to messages of targetBox whose message id is mid
            if (count oldCopies) is 1 and (count msgs) is 0 then return mid
            if (count oldCopies) is not 0 then error "Message-ID bereits im Ziel. Keine weitere Kopie angelegt."
            if (count msgs) is not 1 then error "Originalnachricht nicht eindeutig."
            move (first item of msgs) to targetBox
            repeat 8 times
                if (count (messages of targetBox whose message id is mid)) is 1 then return mid
                delay 0.5
            end repeat
            error "Ziel konnte nicht verifiziert werden. Vor einem erneuten Versuch beide Ordner prüfen."
        end if
        if (count msgs) is not 1 then error "Originalnachricht nicht eindeutig."
        set original to first item of msgs
        if op is "quelle" then return source of original
        if op is "entwurf" then
            set fromAddress to item 5 of argv
            if fromAddress is not in (email addresses of acct) then error "Persönlicher Absender nicht im gewählten Konto."
            set replyBody to read POSIX file (item 6 of argv) as «class utf8»
            set draftMsg to reply original with opening window
            set sender of draftMsg to fromAddress
            set content of draftMsg to replyBody & return & return & (content of draftMsg)
            save draftMsg
            if (extract address from (sender of draftMsg)) is not fromAddress then error "Entwurfsabsender prüfen."
            return subject of draftMsg
        end if
        error "Unbekannter Mailbefehl."
    end tell
end run
