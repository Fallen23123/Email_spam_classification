<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class ScanHistory extends Model
{
    protected $fillable = [
        'user_id', 
        'score', 
        'is_spam',
        'email_preview',
        'email_text',
    ];
}
